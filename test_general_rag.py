"""Regression tests for general-purpose local RAG.

Isolation: destructive index tests run in a temp dir (patched CHROMA_DB_PATH
+ EMBED_CACHE_DIR). Original source documents are never deleted.
Run:  python -m pytest test_general_rag.py -q
"""
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "eval_general", "eval_corpus")


@pytest.fixture()
def isolated(tmp_path):
    import ingest
    import retrieve
    chroma = str(tmp_path / "chroma")
    cache = str(tmp_path / "cache")
    os.makedirs(chroma, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    old = (ingest.CHROMA_DB_PATH, ingest.EMBED_CACHE_DIR,
           retrieve.CHROMA_DB_PATH)
    ingest.CHROMA_DB_PATH = chroma
    ingest.EMBED_CACHE_DIR = cache
    retrieve.CHROMA_DB_PATH = chroma
    retrieve._db_client = None
    retrieve._collection = None
    retrieve._bm25 = None
    retrieve._corpus_data = None
    yield {"chroma": chroma, "cache": cache}
    ingest.CHROMA_DB_PATH, ingest.EMBED_CACHE_DIR, retrieve.CHROMA_DB_PATH = old
    retrieve._db_client = None
    retrieve._collection = None
    retrieve._bm25 = None
    retrieve._corpus_data = None


def test_extract_all_formats():
    import extractors
    expectations = {
        "station.pdf": ("pdf", "page", 2),
        "zephyr.docx": ("docx", "heading", 0),
        "helios.pptx": ("pptx", "slide", 2),
        "inventory.xlsx": ("xlsx", "sheet", 0),
        "crew.csv": ("csv", "sheet", 0),
        "protocol.md": ("md", "heading", 0),
    }
    for fname, (dtype, loc_key, loc_min) in expectations.items():
        dt, blocks = extractors.extract_file(os.path.join(CORPUS, fname))
        assert dt == dtype, fname
        assert blocks, fname
        assert all(b["text"].strip() for b in blocks), fname
        if loc_key == "page":
            assert max(b["page"] for b in blocks) >= loc_min, fname
        elif loc_key == "slide":
            assert max(b["slide"] for b in blocks) >= loc_min, fname
        elif loc_key == "sheet":
            assert any(b["sheet"] for b in blocks), fname
        elif loc_key == "heading":
            assert any(b["heading"] for b in blocks), fname


def test_extract_content_spot_checks():
    import extractors
    _, pdf = extractors.extract_file(os.path.join(CORPUS, "station.pdf"))
    assert any("42 megawatts" in b["text"] for b in pdf)
    _, docx = extractors.extract_file(os.path.join(CORPUS, "zephyr.docx"))
    assert any("1.25 million euros" in b["text"] for b in docx)
    _, pptx = extractors.extract_file(os.path.join(CORPUS, "helios.pptx"))
    assert any("2027-03-14" in b["text"] for b in pptx)
    assert any("cryogenic" in b["text"] for b in pptx)  # speaker notes kept
    _, xlsx = extractors.extract_file(os.path.join(CORPUS, "inventory.xlsx"))
    assert any("SKU-4471" in b["text"] and "Rotterdam" in b["text"] for b in xlsx)
    assert any(b["row_range"] for b in xlsx)
    _, md = extractors.extract_file(os.path.join(CORPUS, "protocol.md"))
    assert any("argon for 90 seconds" in b["text"] for b in md)


def test_unsupported_format_rejected():
    import extractors
    with pytest.raises(extractors.UnsupportedFormatError):
        extractors.extract_file(os.path.join(CORPUS, "notes.exe"))


def test_empty_and_malformed_handled(tmp_path):
    import extractors
    empty = str(tmp_path / "empty.txt")
    open(empty, "w").close()
    with pytest.raises(extractors.ExtractionError):
        extractors.extract_file(empty)
    bad = str(tmp_path / "bad.pdf")
    with open(bad, "wb") as f:
        f.write(b"%PDF-1.4 garbage not a pdf")
    with pytest.raises(extractors.ExtractionError):
        extractors.extract_file(bad)


def test_chunk_metadata_schema():
    import extractors
    import ingest
    dt, blocks = extractors.extract_file(os.path.join(CORPUS, "inventory.xlsx"))
    recs = ingest.make_chunk_records(blocks, "inventory.xlsx", dt, "abc123")
    required = {"file", "doc_id", "doc_type", "chapter", "section", "heading",
                "page", "slide", "sheet", "row_range", "type"}
    for r in recs:
        assert required <= set(r["meta"]), r["meta"]
        assert r["meta"]["doc_type"] == "xlsx"
        assert isinstance(r["meta"]["page"], int)
        assert isinstance(r["meta"]["slide"], int)
        # Chroma-compatible value types only
        for v in r["meta"].values():
            assert isinstance(v, (str, int, float, bool))


def test_ingest_cache_hit_and_invalidation(isolated, tmp_path, capsys):
    import ingest
    src = str(tmp_path / "doc.txt")
    with open(src, "w", encoding="utf-8") as f:
        f.write("Cache test document about geothermal vents. " * 20)
    n1 = ingest.ingest_file(src, recreate=True, original_filename="doc.txt")
    out1 = capsys.readouterr().out
    assert "MISS" in out1
    n2 = ingest.ingest_file(src, recreate=False, original_filename="doc.txt")
    out2 = capsys.readouterr().out
    assert "HIT" in out2
    assert n1 == n2
    # Changed content must never reuse stale embeddings.
    with open(src, "w", encoding="utf-8") as f:
        f.write("Completely different content about desert solar arrays. " * 20)
    ingest.ingest_file(src, recreate=False, original_filename="doc.txt")
    out3 = capsys.readouterr().out
    assert "MISS" in out3


def test_retrieval_location_accuracy(isolated):
    import ingest
    from retrieve import retrieve
    for fname in ["station.pdf", "zephyr.docx", "helios.pptx",
                  "inventory.xlsx", "crew.csv", "protocol.md"]:
        ingest.ingest_file(os.path.join(CORPUS, fname),
                           recreate=(fname == "station.pdf"),
                           original_filename=fname)
    cases = [
        ("Mark-IV reactor outputs how many megawatts", "station.pdf"),
        ("approved budget for Project Zephyr", "zephyr.docx"),
        ("Helios-9 launch window opens when", "helios.pptx"),
        ("quantity of SKU-4471 titanium bolts", "inventory.xlsx"),
        ("commander clearance level Elena Vasquez", "crew.csv"),
        ("flood chamber with argon for how long", "protocol.md"),
    ]
    for q, expected_file in cases:
        hits = retrieve(q, limit=3)
        assert hits, q
        files = [h["metadata"]["file"] for h in hits]
        assert expected_file in files, (q, files)


def test_citations_use_format_locations(isolated):
    import ingest
    from retrieve import retrieve
    from answer import format_citations, location_label
    for fname in ["helios.pptx", "inventory.xlsx", "crew.csv"]:
        ingest.ingest_file(os.path.join(CORPUS, fname),
                           recreate=(fname == "helios.pptx"),
                           original_filename=fname)
    hits = retrieve("Kestrel-2 spectrometer weight", limit=2)
    pptx_hits = [h for h in hits if h["metadata"]["file"] == "helios.pptx"]
    assert pptx_hits
    assert "Slide" in location_label(pptx_hits[0]["metadata"])
    hits = retrieve("SKU-4471 unit price", limit=3)
    xlsx_hits = [h for h in hits if h["metadata"]["file"] == "inventory.xlsx"]
    assert xlsx_hits
    assert "Sheet" in location_label(xlsx_hits[0]["metadata"])
    # CSV citations must never invent page numbers.
    hits = retrieve("Elena Vasquez commander", limit=2)
    csv_hits = [h for h in hits if h["metadata"]["file"] == "crew.csv"]
    assert csv_hits
    assert location_label(csv_hits[0]["metadata"]).find("Page") == -1
    cits = format_citations(hits)
    assert any("crew.csv" in c for c in cits)


def test_empty_workspace_abstains(isolated):
    from retrieve import retrieve
    from answer import answer_question
    assert retrieve("anything at all", limit=3) == []
    res = answer_question("What is the budget?", verbose=False)
    assert "don't have enough information" in res["answer"]
    assert res["citations"] == []


def test_remove_and_unsupported_dont_corrupt(isolated):
    import extractors
    import ingest
    from retrieve import retrieve
    ingest.ingest_file(os.path.join(CORPUS, "station.pdf"),
                       recreate=True, original_filename="station.pdf")
    ingest.ingest_file(os.path.join(CORPUS, "zephyr.docx"),
                       original_filename="zephyr.docx")
    with pytest.raises(extractors.UnsupportedFormatError):
        ingest.ingest_file(os.path.join(CORPUS, "notes.exe"),
                           original_filename="notes.exe")
    docs = ingest.list_documents()
    assert set(docs) == {"station.pdf", "zephyr.docx"}
    assert ingest.remove_document("zephyr.docx") > 0
    docs = ingest.list_documents()
    assert set(docs) == {"station.pdf"}
    hits = retrieve("Aurora Research Station established", limit=2)
    assert hits and hits[0]["metadata"]["file"] == "station.pdf"


def test_duplicate_bytes_new_name_attributed_correctly(isolated):
    """Same content ingested under a second filename must be attributed to
    the new name (cache HIT remaps file metadata), removable by that name,
    and not shown twice in retrieval (near-duplicate guard)."""
    import ingest
    from retrieve import retrieve
    src = os.path.join(CORPUS, "crew.csv")
    ingest.ingest_file(src, recreate=True, original_filename="crew.csv")
    ingest.ingest_file(src, original_filename="crew_snapshot.csv")
    docs = ingest.list_documents()
    assert set(docs) == {"crew.csv", "crew_snapshot.csv"}, docs
    hits = retrieve("Elena Vasquez commander clearance", limit=4)
    assert hits
    assert hits[0]["metadata"]["file"] in {"crew.csv", "crew_snapshot.csv"}
    assert ingest.remove_document("crew_snapshot.csv") > 0
    assert set(ingest.list_documents()) == {"crew.csv"}


def test_oversized_file_rejected(isolated, tmp_path, monkeypatch):
    import extractors
    monkeypatch.setattr(extractors, "MAX_FILE_BYTES", 100)
    big = str(tmp_path / "big.txt")
    with open(big, "w", encoding="utf-8") as f:
        f.write("x" * 200)
    with pytest.raises(extractors.ExtractionError, match="over the"):
        extractors.extract_file(big)


def test_table_row_groups_fit_single_chunk(tmp_path):
    """Table row-groups must fit inside one chunk so the LLM sees the target
    row with few distractors and row_range labels stay accurate (no mid-table
    splits). Regression basis: sensor lookup failed 0/3 with 30-row groups."""
    import extractors
    import ingest
    p = str(tmp_path / "t.csv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("id,zone\n")
        for i in range(25):
            f.write(f"S-{i:04d},Zone{i % 4}\n")
    _, blocks = extractors.extract_file(p)
    assert len(blocks) == 25  # 25 rows, 1 per chunk (CSV)
    for b in blocks:
        assert len(b["text"]) <= ingest.CHUNK_SIZE_CHARS, b["row_range"]
        assert b["row_range"].startswith("rows ")
    recs = ingest.make_chunk_records(blocks, "t.csv", "csv", "deadbeef")
    assert len(recs) == len(blocks)  # no further splitting
    assert recs[0]["meta"]["row_range"] == "rows 2-2"


def test_json_manifest_keys_land_in_retrievable_chunks():
    """A structured JSON manifest must not be indexed as one long blob.

    Regression basis (Oct 2026, real-world corpus): the express manifest's
    `engines.node` key existed and was extracted intact, but the record block
    was 2,866 chars / 254 tokens against a 19-token corpus median. BM25's
    length normalization pushed the value-bearing chunk to rank 28, just
    outside the 20-chunk prefetch window, so `retrieve()` returned only
    awesome_nodejs.md and js1 ("minimum Node version") failed.

    Fix: extract_json uses a smaller record block (600 chars) so key groups
    stay individually retrievable. Asserted here at the extraction level so
    the property holds for ANY json document, not just one manifest.
    """
    import extractors
    import json as _json
    p = str(tmp_path_for_json())
    manifest = {
        "name": "pkg", "description": "x" * 300,
        "dependencies": {f"dep{i}": f"^{i}.0.0" for i in range(40)},
        "devDependencies": {f"dev{i}": f"^{i}.0.0" for i in range(40)},
        "engines": {"node": ">= 18"},
        "scripts": {"test": "jest"},
    }
    with open(p, "w", encoding="utf-8") as f:
        _json.dump(manifest, f)
    _, blocks = extractors.extract_file(p)
    assert len(blocks) > 1, "large manifest must be split into several records"
    # the key/value must survive verbatim in exactly one chunk
    holders = [b for b in blocks if "engines.node" in b["text"]]
    assert len(holders) == 1, holders
    assert ">= 18" in holders[0]["text"]
    # and that chunk must stay small enough to survive BM25 length
    # normalization against short prose chunks
    assert len(holders[0]["text"]) <= 800, len(holders[0]["text"])


def tmp_path_for_json():
    import tempfile
    d = tempfile.mkdtemp(prefix="rag_json_")
    return os.path.join(d, "manifest.json")


def test_thinking_never_leaks_and_prompts_generic():
    from answer import (clean_think_tags, is_empty_answer,
                        EMPTY_ANSWER_MESSAGE, THEORY_PROMPT_TEMPLATE,
                        NUMERICAL_PROMPT_TEMPLATE)
    dirty = "<think>secret reasoning trace</think>Final visible answer."
    assert clean_think_tags(dirty) == "Final visible answer."
    assert "secret" not in clean_think_tags(dirty)
    assert is_empty_answer(EMPTY_ANSWER_MESSAGE)
    assert not is_empty_answer("A real answer.")
    for tpl in (THEORY_PROMPT_TEMPLATE, NUMERICAL_PROMPT_TEMPLATE):
        low = tpl.lower()
        assert "jee" not in low and "neet" not in low and "physics" not in low
        assert "untrusted" in low  # injection guard present


def test_per_document_removal_guard_blocks_chip_reingest():
    """Regression (2026-10-18 real-UI smoke): deleting a document via its ✖
    button reset the chunks, but the Streamlit uploader chip still held the
    file, so the next rerun re-queued it by name and silently re-indexed it
    (server log re-ingested 3 chunks after every delete). The removal guard
    must suppress re-ingestion of a marked-removed name while its chip
    persists."""
    import ingest

    held = ["rccatalog.csv", "rcmd_notes.md"]
    processed, removed = set(), set()

    # Empty session: everything in the uploader is new
    assert ingest.filter_new_uploads(held, processed, removed) == held

    # Document removed via the workspace ✖ button; chip still present
    processed.discard("rccatalog.csv")
    removed.add("rccatalog.csv")
    assert ingest.filter_new_uploads(held, processed, removed) == ["rcmd_notes.md"]


def test_per_document_removal_guard_unblocks_on_chip_removal():
    """When the user removes the uploader chip itself, the blocked name must
    be released so the same file can be re-uploaded later."""
    import ingest

    removed = {"rccatalog.csv"}
    held = ["rcmd_notes.md"]  # chip for rccatalog.csv is gone
    pruned = ingest.prune_removed_files(removed, held)
    assert pruned == set()

    held_again = ["rcmd_notes.md", "rccatalog.csv"]  # re-added later
    pruned = ingest.prune_removed_files(removed, held_again)
    assert pruned == {"rccatalog.csv"}


def test_per_document_removal_guard_clears_on_reset_and_reingest():
    """Reset (workspace rebuild per session lifecycle) and a successful
    re-ingest of the same name must clear blocking markers."""
    import ingest

    processed, removed = {"a.md", "b.csv"}, set()
    # successful ingest of a re-uploaded name clears its marker
    removed.add("b.csv")
    processed.add("b.csv")
    ingest.mark_upload_processed("b.csv", processed, removed)
    assert "b.csv" not in removed

    # Reset clears everything; chips held by the user rebuild the workspace
    cleared = ingest.clear_removal_state(processed, removed)
    assert cleared[0] == set() and cleared[1] == set()
