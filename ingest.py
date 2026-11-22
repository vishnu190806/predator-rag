import hashlib
import json
import os
import re
import uuid
import sys
import fitz  # PyMuPDF
import chromadb

import extractors

# Reconfigure stdout to use UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

# =====================================================
# CONFIGURATION
# =====================================================
# ChromaDB persistent location. Resolved once at import time so every module
# that imports it agrees on a single database directory. Override with the
# PREDATOR_RAG_CHROMA_PATH environment variable; default is ./chroma_db.
CHROMA_DB_PATH = os.environ.get("PREDATOR_RAG_CHROMA_PATH", "./chroma_db")
COLLECTION_NAME = "workspace_chunks"
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
CHUNK_SIZE_CHARS = 1600
CHUNK_OVERLAP_CHARS = 300
EMBED_BATCH_SIZE = 64

# Disk cache for document embeddings (speeds up the intended clean-start
# re-ingest: unchanged files skip re-encoding entirely).
# INVALIDATION: the cache key hashes the raw file bytes + embedding model
# name + extractor version + chunking parameters + CACHE_VERSION. Any changed
# file, extractor update, model swap, or chunking change misses the cache
# automatically. Bump CACHE_VERSION if logic changes in ways the key does
# not capture.
EMBED_CACHE_DIR = "./embed_cache"
# v3: multi-format pipeline (extractors.EXTRACTOR_VERSION + per-format
# metadata). v1/v2 entries auto-miss on this bump.
CACHE_VERSION = "v6"  # v6: JSON record blocks 4000->600 chars (BM25 length norm)

_shared_embedder = None


def get_shared_embedder():
    """Process-wide singleton embedder (CUDA when available)."""
    global _shared_embedder
    if _shared_embedder is None:
        from retrieve import get_embedder
        _shared_embedder = get_embedder()
    return _shared_embedder


def _file_cache_key(file_bytes: bytes) -> str:
    h = hashlib.sha256()
    h.update(file_bytes)
    h.update(b"|" + EMBEDDING_MODEL_NAME.encode())
    h.update(b"|" + extractors.EXTRACTOR_VERSION.encode())
    h.update(f"|{CHUNK_SIZE_CHARS}|{CHUNK_OVERLAP_CHARS}|{CACHE_VERSION}".encode())
    return h.hexdigest()


def doc_id_for_bytes(file_bytes: bytes) -> str:
    return hashlib.sha1(file_bytes).hexdigest()[:12]


def _cache_path(key: str) -> str:
    return os.path.join(EMBED_CACHE_DIR, key + ".json")


def _load_cached_entry(key: str):
    try:
        path = _cache_path(key)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        if entry.get("key") != key or "texts" not in entry or "embeddings" not in entry:
            return None
        if len(entry["texts"]) != len(entry["embeddings"]):
            return None
        return entry
    except Exception:
        return None


def _save_cached_entry(key: str, display_filename: str, chunks, embeddings) -> None:
    try:
        os.makedirs(EMBED_CACHE_DIR, exist_ok=True)
        entry = {
            "key": key,
            "file": display_filename,
            "model": EMBEDDING_MODEL_NAME,
            "texts": [c["text"] for c in chunks],
            "embeddings": embeddings,
            "metadatas": [c["meta"] for c in chunks],
        }
        with open(_cache_path(key), "w", encoding="utf-8") as f:
            json.dump(entry, f)
    except Exception as e:
        print(f"Warning: could not write embedding cache: {e}")


# Regex Patterns for structural extraction (legacy PDF parser)
SECTION_HEADER_RE = re.compile(r"^\s*(\d+\.\d+(?:\.\d+)?)\s+([A-Za-z\s,:'\"\-–’‘ʼ′\ufffd]+)$")
EXAMPLE_START_RE = re.compile(r"^\s*Example\s+(\d+\.\d+)", re.IGNORECASE)
EXERCISE_START_RE = re.compile(r"^\s*(\d+\.\d+)\s+", re.IGNORECASE)
EQUATION_NO_RE = re.compile(r"\(\d+\.\d+[a-z]?\)\s*$")


def is_exercises_header(text):
    return "exercises" in text.lower().strip()


def is_formula_block(text):
    text_clean = text.strip()
    if not text_clean:
        return False
    if EQUATION_NO_RE.search(text_clean):
        return True

    math_symbols = ["\\Delta", "\\theta", "\\pi", "\\omega", "\\alpha", "\\beta", "\\lambda", "\\approx", "\\propto", "=", "+", "-", "*", "/", "^", "cos", "sin", "tan"]
    has_math = any(sym in text_clean for sym in math_symbols)
    if has_math and len(text_clean) < 250:
        alpha_count = sum(1 for c in text_clean if c.isalpha())
        math_chars = set("+-*/=^()_[]{}<>\u03b1\u03b2\u03b3\u03b4\u03b5\u03b8\u03bb\u03c0\u03c3\u03c9\u0394\\")
        math_count = sum(1 for c in text_clean if c in math_chars or c.isdigit())
        total = len(text_clean)
        if total > 0 and (math_count / total > 0.35 or alpha_count / total < 0.6):
            return True
    return False


def parse_pdf(file_path):
    print(f"Parsing: {os.path.basename(file_path)}")
    doc = fitz.open(file_path)

    current_chapter = "Unknown Chapter"
    current_section = "Unknown Section"
    in_exercises = False

    extracted_items = []
    current_example = None
    current_exercise = None

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_val = page_num + 1
        blocks = page.get_text("blocks")

        blocks = sorted(blocks, key=lambda b: (b[1], b[0]))

        for b in blocks:
            x0, y0, x1, y1, text, block_no, block_type = b
            text_clean = text.strip()
            if not text_clean:
                continue

            if "reprint" in text_clean.lower() or text_clean.lower() == "physics":
                continue
            if re.match(r"^physics\s+\d+$", text_clean.lower()):
                continue
            if re.match(r"^[a-z,\s]+power\s+\d+$", text_clean.lower()):
                continue
            if re.match(r"^[a-z,\s]+gravitation\s+\d+$", text_clean.lower()):
                continue
            if text_clean.isdigit():
                continue

            if "CHAPTER" in text_clean and len(text_clean) < 100:
                if current_example:
                    extracted_items.append({
                        "text": "\n\n".join(current_example["text_blocks"]),
                        "type": "example",
                        "section": current_example["section"],
                        "chapter": current_example["chapter"],
                        "page": current_example["start_page"]
                    })
                    current_example = None
                if current_exercise:
                    extracted_items.append({
                        "text": "\n\n".join(current_exercise["text_blocks"]),
                        "type": "exercise",
                        "section": current_exercise["section"],
                        "chapter": current_exercise["chapter"],
                        "page": current_exercise["start_page"]
                    })
                    current_exercise = None

                current_chapter = text_clean
                in_exercises = False
                continue

            if is_exercises_header(text_clean) and len(text_clean) < 50:
                in_exercises = True
                current_section = "Exercises"
                if current_example:
                    extracted_items.append({
                        "text": "\n\n".join(current_example["text_blocks"]),
                        "type": "example",
                        "section": current_example["section"],
                        "chapter": current_example["chapter"],
                        "page": current_example["start_page"]
                    })
                    current_example = None
                continue

            sec_match = SECTION_HEADER_RE.match(text_clean)
            if sec_match and len(text_clean) < 120:
                current_section = text_clean
                in_exercises = False
                if current_example:
                    extracted_items.append({
                        "text": "\n\n".join(current_example["text_blocks"]),
                        "type": "example",
                        "section": current_example["section"],
                        "chapter": current_example["chapter"],
                        "page": current_example["start_page"]
                    })
                    current_example = None
                continue

            if in_exercises:
                ex_match = EXERCISE_START_RE.match(text_clean)
                if ex_match:
                    if current_exercise:
                        extracted_items.append({
                            "text": "\n\n".join(current_exercise["text_blocks"]),
                            "type": "exercise",
                            "section": current_exercise["section"],
                            "chapter": current_exercise["chapter"],
                            "page": current_exercise["start_page"]
                        })
                    current_exercise = {
                        "text_blocks": [text_clean],
                        "start_page": page_val,
                        "section": current_section,
                        "chapter": current_chapter,
                        "exercise_id": ex_match.group(1)
                    }
                else:
                    if current_exercise:
                        current_exercise["text_blocks"].append(text_clean)
                    else:
                        extracted_items.append({
                            "text": text_clean,
                            "type": "theory",
                            "section": current_section,
                            "chapter": current_chapter,
                            "page": page_val
                        })
                continue

            ex_start_match = EXAMPLE_START_RE.match(text_clean)
            if ex_start_match:
                if current_example:
                    extracted_items.append({
                        "text": "\n\n".join(current_example["text_blocks"]),
                        "type": "example",
                        "section": current_example["section"],
                        "chapter": current_example["chapter"],
                        "page": current_example["start_page"]
                    })
                current_example = {
                    "text_blocks": [text_clean],
                    "start_page": page_val,
                    "section": current_section,
                    "chapter": current_chapter,
                    "example_id": ex_start_match.group(1)
                }
                if "⊳" in text_clean:
                    extracted_items.append({
                        "text": "\n\n".join(current_example["text_blocks"]),
                        "type": "example",
                        "section": current_example["section"],
                        "chapter": current_example["chapter"],
                        "page": current_example["start_page"]
                    })
                    current_example = None
                continue

            if current_example:
                current_example["text_blocks"].append(text_clean)
                if "⊳" in text_clean:
                    extracted_items.append({
                        "text": "\n\n".join(current_example["text_blocks"]),
                        "type": "example",
                        "section": current_example["section"],
                        "chapter": current_example["chapter"],
                        "page": current_example["start_page"]
                    })
                    current_example = None
                continue

            if is_formula_block(text_clean):
                extracted_items.append({
                    "text": text_clean,
                    "type": "formula",
                    "section": current_section,
                    "chapter": current_chapter,
                    "page": page_val
                })
            else:
                extracted_items.append({
                    "text": text_clean,
                    "type": "theory",
                    "section": current_section,
                    "chapter": current_chapter,
                    "page": page_val
                })

    if current_example:
        extracted_items.append({
            "text": "\n\n".join(current_example["text_blocks"]),
            "type": "example",
            "section": current_example["section"],
            "chapter": current_example["chapter"],
            "page": current_example["start_page"]
        })
    if current_exercise:
        extracted_items.append({
            "text": "\n\n".join(current_exercise["text_blocks"]),
            "type": "exercise",
            "section": current_exercise["section"],
            "chapter": current_exercise["chapter"],
            "page": current_exercise["start_page"]
        })

    return extracted_items


def chunk_parsed_items(extracted_items, chunk_size_chars=1600, overlap_chars=300):
    chunks = []
    current_theory_run = []
    current_sec = None
    current_chap = None
    current_page = None

    def flush_theory_run():
        nonlocal current_theory_run
        if not current_theory_run:
            return

        full_text = "\n\n".join([item["text"] for item in current_theory_run])
        sec = current_theory_run[0]["section"]
        chap = current_theory_run[0]["chapter"]
        page = current_theory_run[0]["page"]

        if len(full_text) <= chunk_size_chars:
            chunks.append({
                "text": full_text,
                "type": "theory",
                "section": sec,
                "chapter": chap,
                "page": page
            })
        else:
            start = 0
            while start < len(full_text):
                end = start + chunk_size_chars
                if end < len(full_text):
                    split_idx = full_text.rfind("\n\n", end - 200, end)
                    if split_idx != -1:
                        end = split_idx + 2
                    else:
                        split_idx = full_text.rfind("\n", end - 100, end)
                        if split_idx != -1:
                            end = split_idx + 1

                chunk_text = full_text[start:end].strip()
                if chunk_text:
                    chunks.append({
                        "text": chunk_text,
                        "type": "theory",
                        "section": sec,
                        "chapter": chap,
                        "page": page
                    })

                start = end - overlap_chars
                if start >= len(full_text) - 100:
                    break
        current_theory_run = []

    for item in extracted_items:
        if item["type"] == "theory":
            if (current_sec is not None and item["section"] != current_sec) or \
               (current_chap is not None and item["chapter"] != current_chap) or \
               (current_page is not None and item["page"] != current_page):
                flush_theory_run()
            current_sec = item["section"]
            current_chap = item["chapter"]
            current_page = item["page"]
            current_theory_run.append(item)
        else:
            flush_theory_run()
            chunks.append(item)

    flush_theory_run()
    return chunks


# =====================================================
# GENERAL-PURPOSE PIPELINE (multi-format)
# =====================================================
# Structural units that must never merge across a boundary: a PDF page, a
# slide, a spreadsheet row-group, a headed section. Small text blocks in the
# same unit are concatenated; oversized units split on paragraph boundaries.
ATOMIC_TYPES = {"slide", "table", "record", "heading", "note", "formula",
                "example", "exercise", "code"}


def _split_long_text(text, chunk_size_chars, overlap_chars):
    parts = []
    start = 0
    while start < len(text):
        end = start + chunk_size_chars
        if end < len(text):
            split_idx = text.rfind("\n\n", max(start, end - 200), end)
            if split_idx != -1:
                end = split_idx + 2
            else:
                # One-line-table rows are frequently far longer than 100
                # chars (USGS CSV rows ~430 chars, World Bank GDP rows ~170
                # with 14-decimal values); with the old 100-char window the
                # boundary cut a row MID-VALUE — measured Oct 17 2026: a
                # World Bank chunk began with the orphan fragment
                # "304749811", the severed tail of Japan's 2021 GDP growth
                # value "2.21610304749811". Search far enough back to find
                # a real line end (450 chars covers both row widths) so
                # table rows stay whole.
                split_idx = text.rfind("\n", max(start, end - 450), end)
                if split_idx != -1:
                    end = split_idx + 1
        part = text[start:end].strip()
        if part:
            parts.append(part)
        nxt = end - overlap_chars
        if nxt <= start or start >= len(text) - 100:
            break
        start = nxt
    return parts or [text.strip()]


def chunk_blocks(blocks, chunk_size_chars=1600, overlap_chars=300):
    """Group extractor blocks into chunks without crossing boundaries."""
    chunks = []

    def unit_key(b):
        if b.get("slide"):
            return ("slide", b["slide"])
        if b.get("sheet"):
            return ("sheet", b["sheet"], b.get("row_range", ""))
        if b.get("page"):
            return ("page", b["page"], b.get("heading", ""))
        return ("heading", b.get("heading", ""))

    run = []
    run_key = None

    def flush_run():
        nonlocal run
        if not run:
            return
        first = run[0]
        if len(run) == 1 and run[0]["chunk_type"] in ATOMIC_TYPES:
            chunks.append(run[0])
        else:
            joined = "\n\n".join(b["text"] for b in run)
            if len(joined) <= chunk_size_chars:
                merged = dict(first)
                merged["text"] = joined
                chunks.append(merged)
            else:
                for part in _split_long_text(joined, chunk_size_chars,
                                             overlap_chars):
                    c = dict(first)
                    c["text"] = part
                    chunks.append(c)
        run = []

    for b in blocks:
        if b["chunk_type"] in ATOMIC_TYPES and b["chunk_type"] != "text":
            flush_run()
            if len(b["text"]) <= chunk_size_chars:
                chunks.append(b)
            else:
                for part in _split_long_text(b["text"], chunk_size_chars,
                                             overlap_chars):
                    c = dict(b)
                    c["text"] = part
                    chunks.append(c)
            run_key = None
        else:
            key = unit_key(b)
            if run_key is not None and key != run_key:
                flush_run()
            run_key = key
            run.append(b)
    flush_run()
    return [c for c in chunks if c["text"].strip()]


def _with_heading_prefix(text, heading):
    if heading:
        return f"[{heading}]\n{text}"
    return text


def make_chunk_records(blocks, display_filename, doc_type, doc_id,
                       chunk_size_chars=1600, overlap_chars=300):
    """Chunk blocks and attach full citation metadata. Returns a list of
    {"text", "meta"} where meta keeps back-compat keys (file/chapter/
    section/page/type) plus doc_type/slide/sheet/row_range/heading/doc_id."""
    chunked = chunk_blocks(blocks, chunk_size_chars, overlap_chars)
    records = []
    for i, c in enumerate(chunked):
        heading = c.get("heading", "")
        section = heading or "General"
        meta = {
            "file": display_filename,
            "doc_id": doc_id,
            "doc_type": doc_type,
            "chapter": heading.split(" > ")[0] if heading else "",
            "section": section,
            "heading": heading,
            "page": int(c.get("page", 0) or 0),
            "slide": int(c.get("slide", 0) or 0),
            "sheet": c.get("sheet", ""),
            "row_range": c.get("row_range", ""),
            "type": c.get("chunk_type", "text"),
        }
        records.append({"text": _with_heading_prefix(c["text"], heading),
                        "meta": meta, "index": i})
    return records


def _parse_and_chunk_pdf(file_path, display_filename):
    """Legacy physics-aware PDF path, upgraded with shared metadata keys."""
    with open(file_path, "rb") as f:
        pdf_bytes = f.read()
    items = parse_pdf(file_path)
    chunks = chunk_parsed_items(items,
                                chunk_size_chars=CHUNK_SIZE_CHARS,
                                overlap_chars=CHUNK_OVERLAP_CHARS)
    doc_id = doc_id_for_bytes(pdf_bytes)
    records = []
    for i, c in enumerate(chunks):
        meta = {
            "file": display_filename,
            "doc_id": doc_id,
            "doc_type": "pdf",
            "chapter": c.get("chapter", ""),
            "section": c.get("section", ""),
            "heading": c.get("section", ""),
            "page": int(c.get("page", 0) or 0),
            "slide": 0,
            "sheet": "",
            "row_range": "",
            "type": c.get("type", "theory"),
        }
        records.append({"text": c["text"], "meta": meta, "index": i})
    return pdf_bytes, records


def _parse_and_chunk_generic(file_path, display_filename):
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    doc_type, blocks = extractors.extract_file(file_path, display_filename)
    if doc_type == "pdf":
        # PDFs keep the structure-aware legacy parser (verified quality);
        # fall back to generic blocks only if it finds nothing.
        items = parse_pdf(file_path)
        if items:
            chunks = chunk_parsed_items(items,
                                        chunk_size_chars=CHUNK_SIZE_CHARS,
                                        overlap_chars=CHUNK_OVERLAP_CHARS)
            doc_id = doc_id_for_bytes(file_bytes)
            records = []
            for i, c in enumerate(chunks):
                meta = {
                    "file": display_filename,
                    "doc_id": doc_id,
                    "doc_type": "pdf",
                    "chapter": c.get("chapter", ""),
                    "section": c.get("section", ""),
                    "heading": c.get("section", ""),
                    "page": int(c.get("page", 0) or 0),
                    "slide": 0,
                    "sheet": "",
                    "row_range": "",
                    "type": c.get("type", "theory"),
                }
                records.append({"text": c["text"], "meta": meta, "index": i})
            return file_bytes, records
    doc_id = doc_id_for_bytes(file_bytes)
    records = make_chunk_records(blocks, display_filename, doc_type, doc_id,
                                 CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS)
    return file_bytes, records


def _embed_chunks_cached(file_bytes, display_filename, records):
    """Return (texts, embeddings, metadatas), using the disk cache on hit.

    The cache key is content-addressed (no filename), so identical bytes
    ingested under a different name HIT. Metadatas are therefore remapped
    to the requested display filename on every HIT — otherwise duplicate
    content would be misattributed to whichever name was ingested first
    (wrong citations, broken per-file removal).
    """
    key = _file_cache_key(file_bytes)
    entry = _load_cached_entry(key)
    if entry is not None and len(entry["texts"]) == len(records) and all(
            a == b for a, b in zip(entry["texts"],
                                   [r["text"] for r in records])):
        print(f"Embedding cache HIT for '{display_filename}' "
              f"({len(records)} chunks, skipping re-encode).")
        metas = [dict(m, file=display_filename) for m in entry["metadatas"]]
        return entry["texts"], entry["embeddings"], metas
    print(f"Embedding cache MISS for '{display_filename}' "
          f"({len(records)} chunks, encoding...).")
    embedder = get_shared_embedder()
    texts = [r["text"] for r in records]
    embeddings = embedder.encode(texts, batch_size=EMBED_BATCH_SIZE,
                                 show_progress_bar=False).tolist()
    metadatas = [r["meta"] for r in records]
    _save_cached_entry(key, display_filename, records, embeddings)
    return texts, embeddings, metadatas


def _add_to_collection(collection, texts, embeddings, metadatas):
    batch_size = EMBED_BATCH_SIZE
    nbatches = (len(texts) + batch_size - 1) // batch_size
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        ids = [str(uuid.uuid4()) for _ in batch_texts]
        collection.add(
            ids=ids,
            embeddings=embeddings[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size],
            documents=batch_texts
        )
        print(f"Ingested batch {i // batch_size + 1}/{nbatches}")


def _connect(recreate):
    db_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    if recreate:
        try:
            db_client.delete_collection(COLLECTION_NAME)
            print(f"Deleted existing collection '{COLLECTION_NAME}' for a clean start.")
        except Exception:
            pass
        # Invalidate retrieve.py's cached collection handle so the next
        # retrieval re-connects to the fresh collection, not a deleted one.
        try:
            import retrieve as _r
            _r.invalidate_collection_cache()
        except Exception:
            pass
    return db_client.get_or_create_collection(COLLECTION_NAME)


def ingest_pdfs(data_dir="./data", recreate=True):
    pdf_files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print(f"No PDFs found in {data_dir}!")
        return

    staged = []
    for pdf in pdf_files:
        pdf_bytes, records = _parse_and_chunk_pdf(pdf, os.path.basename(pdf))
        staged.append((pdf_bytes, os.path.basename(pdf), records))
    total = sum(len(r) for _, _, r in staged)
    print(f"\nTotal chunks to index: {total}")

    all_texts, all_embs, all_metas = [], [], []
    for pdf_bytes, disp, records in staged:
        texts, embs, metas = _embed_chunks_cached(pdf_bytes, disp, records)
        all_texts.extend(texts)
        all_embs.extend(embs)
        all_metas.extend(metas)

    print(f"Connecting to persistent ChromaDB at: {CHROMA_DB_PATH}")
    collection = _connect(recreate)
    _add_to_collection(collection, all_texts, all_embs, all_metas)

    print(f"\n==========================================")
    print(f"INGESTION COMPLETE: {collection.count()} chunks stored in ChromaDB.")
    print(f"==========================================")


def ingest_single_pdf(file_path, recreate=False, original_filename=None):
    print(f"Ingesting single PDF: {file_path}")
    display_filename = original_filename if original_filename else os.path.basename(file_path)

    pdf_bytes, records = _parse_and_chunk_pdf(file_path, display_filename)
    print(f"Total chunks to index: {len(records)}")

    texts, embeddings, metadatas = _embed_chunks_cached(pdf_bytes, display_filename, records)

    collection = _connect(recreate)
    _add_to_collection(collection, texts, embeddings, metadatas)

    print(f"Single PDF Ingestion complete: {os.path.basename(file_path)}")


def ingest_file(file_path, recreate=False, original_filename=None):
    """Ingest one supported file of any format. Returns chunk count.

    Raises extractors.UnsupportedFormatError / ExtractionError with a
    clear message; never partially indexes a failed file.
    """
    display_filename = original_filename if original_filename else os.path.basename(file_path)
    print(f"Ingesting file: {display_filename}")
    file_bytes, records = _parse_and_chunk_generic(file_path, display_filename)
    print(f"Total chunks to index: {len(records)}")
    texts, embeddings, metadatas = _embed_chunks_cached(file_bytes, display_filename, records)
    collection = _connect(recreate)
    _add_to_collection(collection, texts, embeddings, metadatas)
    print(f"Ingestion complete: {display_filename} ({len(records)} chunks)")
    return len(records)


def ingest_files(paths, recreate=False, progress_cb=None):
    """Ingest many files. Returns (ok, errors): ok maps filename->chunks,
    errors maps filename->message. One bad file never blocks the rest."""
    ok, errors = {}, {}
    first = recreate
    for p in paths:
        name = os.path.basename(p)
        try:
            ok[name] = ingest_file(p, recreate=first)
            first = False
        except (extractors.UnsupportedFormatError,
                extractors.ExtractionError, OSError) as e:
            errors[name] = str(e)
        if progress_cb:
            progress_cb(name)
    return ok, errors


def remove_document(filename):
    """Delete all chunks for one file. Returns deleted count."""
    db_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    try:
        collection = db_client.get_collection(COLLECTION_NAME)
    except Exception:
        return 0
    try:
        res = collection.get(where={"file": filename}, include=[])
        ids = res.get("ids", [])
    except Exception:
        ids = []
    if ids:
        collection.delete(ids=ids)
    # Invalidate in-memory BM25 snapshot if present.
    try:
        import retrieve as _r
        _r._bm25 = None
        _r._corpus_data = None
    except Exception:
        pass
    # Drop that file's embedding-cache entry so re-upload re-encodes.
    try:
        for fn in os.listdir(EMBED_CACHE_DIR):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(EMBED_CACHE_DIR, fn), encoding="utf-8") as f:
                entry = json.load(f)
            if entry.get("file") == filename:
                os.remove(os.path.join(EMBED_CACHE_DIR, fn))
    except Exception:
        pass
    return len(ids)


def clear_collection():
    db_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    try:
        db_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    try:
        import retrieve as _r
        _r._bm25 = None
        _r._corpus_data = None
    except Exception:
        pass


def list_documents():
    """Return {filename: chunk_count} for the current workspace."""
    db_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    try:
        collection = db_client.get_collection(COLLECTION_NAME)
    except Exception:
        return {}
    try:
        res = collection.get(include=["metadatas"])
    except Exception:
        return {}
    counts = {}
    for m in res.get("metadatas", []) or []:
        f = (m or {}).get("file", "?")
        counts[f] = counts.get(f, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Workspace upload/removal state guards (pure helpers, UI-agnostic).
#
# Regression context (2026-10-18 real-UI smoke): Streamlit file_uploader
# chips persist for the whole session, but delete_document removed the
# file's chunks and dropped it from processed_files, so the next rerun
# silently re-queued and re-indexed it ("remove" appeared to do nothing).
# ---------------------------------------------------------------------------

def filter_new_uploads(held_names, processed_files, removed_files):
    """Return the uploader names that still need indexing this run.

    Names marked in removed_files are skipped until their uploader chip
    disappears (or they are re-ingested intentionally)."""
    return [n for n in held_names
            if n not in processed_files and n not in removed_files]


def prune_removed_files(removed_files, held_names):
    """Return the subset of removed markers whose uploader chip is still in
    the current uploader value. Non-mutating: markers for chips the user
    dropped are released so the same file can be re-uploaded later."""
    return removed_files & set(held_names)


def mark_upload_processed(name, processed_files, removed_files):
    """Record a completed ingest and clear that name's removal marker."""
    processed_files.add(name)
    removed_files.discard(name)


def clear_removal_state(processed_files, removed_files):
    """Reset handler: empty every marker; the workspace is rebuilt from the
    chips the user still holds (documented per-session lifecycle)."""
    processed_files.clear()
    removed_files.clear()
    return processed_files, removed_files


if __name__ == "__main__":
    ingest_pdfs(recreate=True)
