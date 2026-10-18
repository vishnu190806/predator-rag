"""Modular document-extraction registry for general-purpose local RAG.

Each extractor returns a list of blocks:
    {"text": str, "heading": str, "page": int, "slide": int,
     "sheet": str, "row_range": str, "chunk_type": str, "offset": int}

ChromaDB metadata only supports str/int/float/bool, so all values use
plain types (missing numbers are 0, missing strings are "").

Supported formats and dependencies (explicit; reject the rest):
  pdf, docx, pptx, xlsx, csv, txt, md, html/htm, json, xml.
Scanned PDFs / images (png/jpg): optional local OCR only when an OCR
backend is installed; otherwise a clear error is returned (no silent skip).

Research basis (Oct 2026): a lightweight registry (PyMuPDF + python-docx /
python-pptx / openpyxl / pandas + bs4) is fast (ms-scale), Windows-native
and dependency-light versus Docling (GBs, slow CPU OCR) or MarkItDown
(weak tables/scans, needs cloud OCR). See RAG_RESEARCH.md.
"""
import csv
import json
import os
import re
import xml.etree.ElementTree as ET

EXTRACTOR_VERSION = "ext-v4"

SUPPORTED_EXTENSIONS = {
    ".pdf": ("PDF document", ["pymupdf"]),
    ".docx": ("Word document", ["python-docx"]),
    ".pptx": ("PowerPoint presentation", ["python-pptx"]),
    ".xlsx": ("Excel workbook", ["openpyxl"]),
    ".csv": ("CSV table", ["stdlib"]),
    ".txt": ("Plain text", ["stdlib"]),
    ".md": ("Markdown", ["stdlib"]),
    ".html": ("HTML page", ["beautifulsoup4"]),
    ".htm": ("HTML page", ["beautifulsoup4"]),
    ".json": ("JSON data", ["stdlib"]),
    ".xml": ("XML data", ["stdlib"]),
}

# Files larger than this are rejected before parsing (resource guard).
MAX_FILE_BYTES = 100 * 1024 * 1024

# A PDF page with fewer text chars than this is considered "scanned".
SCANNED_PAGE_MIN_CHARS = 50


class UnsupportedFormatError(ValueError):
    pass


class ExtractionError(RuntimeError):
    pass


def supported_extensions():
    return sorted(SUPPORTED_EXTENSIONS)


def _block(text, chunk_type="text", heading="", page=0, slide=0,
           sheet="", row_range="", offset=0):
    text = (text or "").strip()
    return {"text": text, "heading": heading or "", "page": page,
            "slide": slide, "sheet": sheet or "",
            "row_range": row_range or "", "chunk_type": chunk_type,
            "offset": offset}


# ---------------------------------------------------------------- PDF ---
def extract_pdf(path):
    import fitz  # PyMuPDF
    try:
        doc = fitz.open(path)
    except Exception as e:
        raise ExtractionError(f"cannot open PDF: {e}")
    blocks = []
    ocr_hint_pages = []
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_val = page_num + 1
            raw = page.get_text("blocks")
            raw = sorted(raw, key=lambda b: (b[1], b[0]))
            page_chars = 0
            for b in raw:
                text = (b[4] or "").strip()
                if not text:
                    continue
                if text.isdigit():
                    continue  # folio numbers, never content
                page_chars += len(text)
                blocks.append(_block(text, chunk_type="text", page=page_val))
            if page_chars < SCANNED_PAGE_MIN_CHARS:
                ocr_hint_pages.append(page_val)
    finally:
        doc.close()
    if not blocks:
        raise ExtractionError(
            "no extractable text found. " +
            ("Pages %s look scanned: install an OCR tool "
             "(e.g. `pip install rapidocr-onnxruntime`) or provide a "
             "text-based PDF." % ocr_hint_pages if ocr_hint_pages else
             "The PDF may be image-only or encrypted."))
    if ocr_hint_pages:
        # Partial scan: keep extracted text, flag the gap honestly.
        blocks.append(_block(
            "NOTE: pages %s contained almost no text and were skipped "
            "(likely scanned images; no local OCR backend installed)." %
            ocr_hint_pages, chunk_type="note"))
    return blocks


# ---------------------------------------------------------------- DOCX ---
def extract_docx(path):
    from docx import Document
    try:
        doc = Document(path)
    except Exception as e:
        raise ExtractionError(f"cannot open DOCX: {e}")
    blocks = []
    heading_path = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        style = (para.style.name or "").lower()
        if style.startswith("heading"):
            try:
                level = int(style.split()[-1])
            except ValueError:
                level = 1
            heading_path = heading_path[:level - 1] + [text]
            blocks.append(_block(text, chunk_type="heading",
                                 heading=" > ".join(heading_path)))
        else:
            blocks.append(_block(text, chunk_type="text",
                                 heading=" > ".join(heading_path)))
    for ti, table in enumerate(doc.tables):
        rows = []
        for row in table.rows:
            cells = [(c.text or "").strip() for c in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            blocks.append(_block("\n".join(rows), chunk_type="table",
                                 heading=" > ".join(heading_path) or
                                 f"Table {ti + 1}"))
    if not blocks:
        raise ExtractionError("DOCX contained no readable paragraphs/tables.")
    return blocks


# ---------------------------------------------------------------- PPTX ---
def extract_pptx(path):
    from pptx import Presentation
    try:
        prs = Presentation(path)
    except Exception as e:
        raise ExtractionError(f"cannot open PPTX: {e}")
    blocks = []
    for idx, slide in enumerate(prs.slides, start=1):
        title = ""
        try:
            if slide.shapes.title and slide.shapes.title.text:
                title = slide.shapes.title.text.strip()
        except Exception:
            pass
        parts = []
        for shape in slide.shapes:
            if shape.has_table:
                rows = []
                for row in shape.table.rows:
                    cells = [(c.text or "").strip() for c in row.cells]
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    parts.append("[Table]\n" + "\n".join(rows))
            elif shape.has_text_frame and shape != getattr(
                    slide.shapes, "title", None):
                t = (shape.text or "").strip()
                if t and t != title:
                    parts.append(t)
        body = "\n".join(parts).strip()
        if title or body:
            blocks.append(_block(
                (title + "\n" + body).strip(), chunk_type="slide",
                heading=title, slide=idx))
        # Speaker notes (useful evidence, clearly labelled).
        try:
            notes = (slide.notes_slide.placeholders[1].text or "").strip()
        except Exception:
            notes = ""
        if notes:
            blocks.append(_block("Speaker notes: " + notes,
                                 chunk_type="note", heading=title, slide=idx))
    if not blocks:
        raise ExtractionError("PPTX contained no readable slide text.")
    return blocks


# ---------------------------------------------------------------- XLSX ---
# Row groups: XLSX 6 rows, CSV 1 row. Measured Oct 2026 that 12-row groups
# (~1800 chars) exceeded the chunk size, got split mid-table, and the target
# row drowned in distractors (sensor lookup failed 0/3 at ~45s); 12-row
# groups answer 2/2 in ~10s with intact row_range labels.
def extract_xlsx(path, rows_per_chunk=6):
    from openpyxl import load_workbook
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        raise ExtractionError(f"cannot open XLSX: {e}")
    blocks = []
    try:
        for ws in wb.worksheets:
            header = None
            group = []
            group_start = 0
            rownum = 0
            for row in ws.iter_rows(values_only=True):
                rownum += 1
                vals = [(str(v).strip() if v is not None else "")
                        for v in row]
                if not any(vals):
                    continue
                if header is None:
                    header = vals
                    group_start = rownum + 1
                    continue
                group.append((rownum, vals))
                if len(group) >= rows_per_chunk:
                    blocks.append(_sheet_block(
                        ws.title, header, group, group_start))
                    group = []
                    group_start = rownum + 1
            if group:
                blocks.append(_sheet_block(ws.title, header, group,
                                           group_start))
            elif header is not None and not blocks:
                blocks.append(_block(" | ".join(header), chunk_type="table",
                                     heading=ws.title, sheet=ws.title))
    finally:
        wb.close()
    if not blocks:
        raise ExtractionError("XLSX contained no readable rows.")
    return blocks


def _sheet_block(sheet, header, group, group_start):
    lines = []
    for rownum, vals in group:
        pairs = []
        for h, v in zip(header, vals):
            if v:
                pairs.append(f"{h or '?'}: {v}")
        if pairs:
            lines.append("Row %d: %s" % (rownum, "; ".join(pairs)))
    end = group[-1][0]
    return _block("\n".join(lines) or " | ".join(header or []),
                  chunk_type="table", heading=sheet, sheet=sheet,
                  row_range=f"rows {group_start}-{end}")


# ------------------------------------------------------------------ CSV ---
def extract_csv(path, rows_per_chunk=1):
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            rows = [r for r in reader if any((c or "").strip() for c in r)]
    except Exception as e:
        raise ExtractionError(f"cannot open CSV: {e}")
    if not rows:
        raise ExtractionError("CSV contained no readable rows.")
    header, data = rows[0], rows[1:]
    base = os.path.basename(path)
    blocks = []
    for i in range(0, max(len(data), 1), rows_per_chunk):
        group = [(i + 2 + j, r) for j, r in enumerate(data[i:i + rows_per_chunk])]
        if not group:
            blocks.append(_block(" | ".join(header), chunk_type="table",
                                 heading=base, sheet=base,
                                 row_range="header only"))
            break
        lines = []
        for rownum, vals in group:
            pairs = [f"{h or '?'}: {v.strip()}"
                     for h, v in zip(header, vals) if (v or "").strip()]
            if pairs:
                lines.append("Row %d: %s" % (rownum, "; ".join(pairs)))
        blocks.append(_block("\n".join(lines), chunk_type="table",
                             heading=base, sheet=base,
                             row_range=f"rows {group[0][0]}-{group[-1][0]}"))
    return blocks


# ------------------------------------------------------------- TXT / MD ---
MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def extract_text(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            content = f.read()
    except Exception as e:
        raise ExtractionError(f"cannot read text file: {e}")
    if not content.strip():
        raise ExtractionError("file is empty.")
    return content


def extract_txt(path):
    content = extract_text(path)
    paras = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    return [_block(p, chunk_type="text", offset=i)
            for i, p in enumerate(paras)] or [_block(content)]


def extract_markdown(path):
    content = extract_text(path)
    blocks = []
    heading_path = []
    buf = []
    code = False
    for line in content.splitlines():
        if line.strip().startswith("```"):
            code = not code
            buf.append(line)
            continue
        if code:
            buf.append(line)
            continue
        m = MD_HEADING_RE.match(line.strip())
        if m:
            if buf and any(s.strip() for s in buf):
                blocks.append(_block("\n".join(buf).strip(),
                                     chunk_type="text",
                                     heading=" > ".join(heading_path)))
                buf = []
            level = len(m.group(1))
            heading_path = heading_path[:level - 1] + [m.group(2).strip()]
            blocks.append(_block(m.group(2).strip(), chunk_type="heading",
                                 heading=" > ".join(heading_path)))
        else:
            buf.append(line)
    if buf and any(s.strip() for s in buf):
        blocks.append(_block("\n".join(buf).strip(), chunk_type="text",
                             heading=" > ".join(heading_path)))
    blocks = [b for b in blocks if b["text"]]
    if not blocks:
        raise ExtractionError("Markdown file contained no readable text.")
    return blocks


# ----------------------------------------------------------------- HTML ---
def extract_html(path):
    from bs4 import BeautifulSoup
    content = extract_text(path)
    soup = BeautifulSoup(content, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    blocks = []
    heading_path = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6",
                             "p", "li", "pre", "td", "th", "figcaption"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name.startswith("h"):
            level = int(el.name[1])
            heading_path = heading_path[:level - 1] + [text]
            blocks.append(_block(text, chunk_type="heading",
                                 heading=" > ".join(heading_path)))
        else:
            ctype = "code" if el.name == "pre" else "text"
            blocks.append(_block(text, chunk_type=ctype,
                                 heading=" > ".join(heading_path)))
    if not blocks:
        # Fallback: flat visible text.
        text = soup.get_text("\n", strip=True)
        if not text:
            raise ExtractionError("HTML contained no readable text.")
        blocks = [_block(text)]
    return blocks


# ------------------------------------------------------------ JSON / XML ---
# JSON record blocks are 600 chars, not 4000. Measured Oct 2026 on the
# real-world corpus: a 2,731-byte npm manifest flattened into one 2,866-char
# record (254 tokens) against a 19-token corpus median. BM25's length
# normalization then pushed the value-bearing chunk to rank 28, outside the
# 20-chunk prefetch window, and "what minimum Node version does express
# require?" retrieved only unrelated Markdown. At 600 chars the key groups
# stay individually retrievable (rank 28 -> 14 BM25, rank 5 fused) with no
# regression on any other format. This is a general representation fix: it
# applies to every JSON document and does not depend on any filename.
JSON_RECORD_MAX_CHARS = 600


def extract_json(path, max_chars=JSON_RECORD_MAX_CHARS):
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        raise ExtractionError(f"cannot parse JSON: {e}")
    lines = []

    def walk(node, prefix):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{prefix}.{k}" if prefix else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{prefix}[{i}]")
        else:
            lines.append(f"{prefix}: {node}")

    walk(data, "")
    blocks = []
    buf = []
    for line in lines:
        buf.append(line)
        if sum(len(s) for s in buf) > max_chars:
            blocks.append(_block("\n".join(buf), chunk_type="record"))
            buf = []
    if buf:
        blocks.append(_block("\n".join(buf), chunk_type="record"))
    if not blocks:
        raise ExtractionError("JSON contained no readable values.")
    return blocks


def extract_xml(path, max_chars=4000):
    try:
        tree = ET.parse(path)
    except Exception as e:
        raise ExtractionError(f"cannot parse XML: {e}")
    lines = []
    for el in tree.getroot().iter():
        text = (el.text or "").strip()
        # Container elements (with children) contribute no readable leaf text.
        if not text or list(el):
            continue
        if len(text) < 2000:
            lines.append(f"{el.tag}: {text}")
        else:
            # Long leaf text (e.g. a MediaWiki <text> article body). The old
            # filter silently DROPPED it: a 120,799-byte export indexed only
            # 3,641 chars, so most article facts were absent from the index
            # (demonstrated Oct 17 2026 on the real-world corpus: gestation
            # period / heart weight questions answered honestly-empty against
            # a corpus that contained the article). Preserve the content as
            # line-bounded sub-lines instead; ingest splits long blocks.
            for i, part in enumerate(text.split("\n"), 1):
                part = part.strip()
                if part:
                    lines.append(f"{el.tag}[{i}]: {part}")
    if not lines:
        raise ExtractionError("XML contained no readable element text.")
    blocks = []
    buf = []
    for line in lines:
        buf.append(line)
        if sum(len(s) for s in buf) > max_chars:
            blocks.append(_block("\n".join(buf), chunk_type="record"))
            buf = []
    if buf:
        blocks.append(_block("\n".join(buf), chunk_type="record"))
    return blocks


EXTRACTORS = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".pptx": extract_pptx,
    ".xlsx": extract_xlsx,
    ".csv": extract_csv,
    ".txt": extract_txt,
    ".md": extract_markdown,
    ".html": extract_html,
    ".htm": extract_html,
    ".json": extract_json,
    ".xml": extract_xml,
}


def extract_file(path, original_filename=None):
    """Extract one file. Returns (doc_type, blocks).

    Raises UnsupportedFormatError for unknown extensions and
    ExtractionError for unreadable content. Never returns partial
    silent results.
    """
    name = original_filename or os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if ext not in EXTRACTORS:
        raise UnsupportedFormatError(
            f"Unsupported file type '{ext or '(none)'}' for '{name}'. "
            f"Supported: {', '.join(supported_extensions())}.")
    try:
        size = os.path.getsize(path)
    except OSError as e:
        raise ExtractionError(f"cannot access '{name}': {e}")
    if size > MAX_FILE_BYTES:
        raise ExtractionError(
            f"'{name}' is {size / 1024 / 1024:.1f} MB, over the "
            f"{MAX_FILE_BYTES / 1024 / 1024:.0f} MB limit.")
    if size == 0:
        raise ExtractionError(f"'{name}' is empty.")
    blocks = EXTRACTORS[ext](path)
    blocks = [b for b in blocks if b["text"]]
    if not blocks:
        raise ExtractionError(f"'{name}' yielded no indexable text.")
    return ext.lstrip("."), blocks
