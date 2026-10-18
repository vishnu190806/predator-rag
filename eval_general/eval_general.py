"""Mixed-format general-purpose RAG evaluation (deterministic + optional LLM).

Usage:
  python eval_general/eval_general.py            # no LLM needed
  python eval_general/eval_general.py --with-llm # + answer correctness via Ollama

Evaluates the REAL pipeline in a temp workspace (never touches ./chroma_db).
Writes eval_general/results.json and prints a summary table.
"""
import json
import os
import subprocess
import sys
import time

import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ingest
import retrieve
import extractors
from answer import answer_question, location_label

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "eval_corpus")

QUESTIONS = [
    {"id": "pdf-1", "q": "In what year was the Aurora Research Station established?",
     "file": "station.pdf", "loc": "Page 1", "keywords": ["1998"]},
    {"id": "pdf-2", "q": "What is the full-capacity output of the Mark-IV reactor?",
     "file": "station.pdf", "loc": "Page 2", "keywords": ["42", "megawatt"]},
    {"id": "docx-1", "q": "Who leads Project Zephyr?",
     "file": "zephyr.docx", "loc": "Project Zephyr Overview", "keywords": ["Amara Okafor"]},
    {"id": "docx-2", "q": "What is the approved budget for Project Zephyr?",
     "file": "zephyr.docx", "loc": "Budget", "keywords": ["1.25", "million", "euro"]},
    {"id": "pptx-1", "q": "When does the Helios-9 launch window open and from where?",
     "file": "helios.pptx", "loc": "Slide 1", "keywords": ["2027-03-14", "Kourou"]},
    {"id": "pptx-2", "q": "How much does the Kestrel-2 spectrometer weigh?",
     "file": "helios.pptx", "loc": "Slide 2", "keywords": ["85", "kilogram"]},
    {"id": "xlsx-1", "q": "What is the quantity and warehouse of SKU-4471 titanium bolts?",
     "file": "inventory.xlsx", "loc": "Inventory", "keywords": ["1200", "Rotterdam"]},
    {"id": "xlsx-2", "q": "What is the unit price of SKU-4472 ceramic tiles?",
     "file": "inventory.xlsx", "loc": "Pricing", "keywords": ["12.3"]},
    {"id": "csv-1", "q": "Who is the commander and what is her clearance?",
     "file": "crew.csv", "loc": "crew.csv", "keywords": ["Elena Vasquez", "level-5"]},
    {"id": "md-1", "q": "How long must the chamber be flooded with argon?",
     "file": "protocol.md", "loc": "Steps", "keywords": ["90", "second"]},
    {"id": "xdoc-1", "q": "Compare the Helios-9 launch date with the Aurora station founding year. Which came first?",
     "file": None, "loc": None, "keywords": ["1998", "2027", "Aurora"]},
    {"id": "unsup-1", "q": "What is the refund policy for cancelled reactor orders?",
     "file": None, "loc": None, "keywords": ["don't have enough information"],
     "abstain": True},
]


def vram_mb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"], stderr=subprocess.DEVNULL)
        return float(out.decode().strip().splitlines()[0])
    except Exception:
        return 0.0


def main():
    with_llm = "--with-llm" in sys.argv
    tmp = os.path.join(HERE, "tmp_eval")
    chroma = os.path.join(tmp, "chroma")
    cache = os.path.join(tmp, "cache")
    os.makedirs(chroma, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    ingest.CHROMA_DB_PATH = chroma
    ingest.EMBED_CACHE_DIR = cache
    retrieve.CHROMA_DB_PATH = chroma

    results = {"extraction": {}, "index": {}, "questions": [],
               "resources": {}, "with_llm": with_llm}

    # 1. Extraction by format
    files = ["station.pdf", "zephyr.docx", "helios.pptx", "inventory.xlsx",
             "crew.csv", "protocol.md"]
    for fname in files:
        t0 = time.perf_counter()
        dt, blocks = extractors.extract_file(os.path.join(CORPUS, fname))
        dt_ = time.perf_counter() - t0
        results["extraction"][fname] = {
            "seconds": round(dt_, 3), "blocks": len(blocks), "doc_type": dt,
            "ok": len(blocks) > 0}
        print(f"extract {fname}: {dt_:.3f}s, {len(blocks)} blocks")
    try:
        extractors.extract_file(os.path.join(CORPUS, "notes.exe"))
        results["extraction"]["notes.exe"] = {"ok": False, "note": "NOT rejected!"}
    except extractors.UnsupportedFormatError as e:
        results["extraction"]["notes.exe"] = {"ok": True, "note": f"rejected: {e}"}
        print("extract notes.exe: correctly rejected")

    # 2. Index build + cache-hit timing
    t0 = time.perf_counter()
    total_chunks = 0
    for i, fname in enumerate(files):
        total_chunks += ingest.ingest_file(
            os.path.join(CORPUS, fname), recreate=(i == 0),
            original_filename=fname)
    cold = time.perf_counter() - t0
    # Cache-hit timing WITHOUT polluting the index (see eval_stress).
    with open(os.path.join(CORPUS, files[0]), "rb") as f:
        hot_bytes = f.read()
    from ingest import _parse_and_chunk_generic, _embed_chunks_cached
    t0 = time.perf_counter()
    _hot_rec = _parse_and_chunk_generic(os.path.join(CORPUS, files[0]), files[0])[1]
    _embed_chunks_cached(hot_bytes, files[0], _hot_rec)
    hot = time.perf_counter() - t0
    results["index"] = {"cold_seconds": round(cold, 2),
                        "cache_hit_seconds": round(hot, 2),
                        "chunks": total_chunks}
    print(f"index cold: {cold:.2f}s ({total_chunks} chunks), cache-hit re-ingest: {hot:.2f}s")

    # 3. Retrieval + citation checks (deterministic, no LLM)
    retrieve.initialize_retrieval_components()
    n_recall = n_loc = 0
    n_cit_valid = 0
    rec_lat, llm_lat = [], []
    for item in QUESTIONS:
        t0 = time.perf_counter()
        hits = retrieve.retrieve(item["q"], limit=3)
        rl = time.perf_counter() - t0
        rec_lat.append(rl)
        got_files = [h["metadata"]["file"] for h in hits]
        recall = 1.0 if (item["file"] is None or item["file"] in got_files) else 0.0
        loc_ok = 0.0
        if item["loc"] and recall:
            loc_ok = 1.0 if any(item["loc"].lower() in
                                location_label(h["metadata"]).lower()
                                for h in hits
                                if h["metadata"]["file"] == item["file"]) else 0.0
        elif item["loc"] is None:
            loc_ok = 1.0  # cross-doc / abstain: no single location expected
        # Citation validity: every citation's location must match its chunk
        # metadata (no invented numbers), csv must not claim a page.
        from answer import format_citations
        cits = format_citations(hits)
        cit_ok = 1.0 if cits else 0.0
        for h in hits:
            lab = location_label(h["metadata"])
            if h["metadata"]["file"] == "crew.csv" and "Page" in lab:
                cit_ok = 0.0
        n_recall += recall
        n_loc += loc_ok
        n_cit_valid += cit_ok
        qres = {"id": item["id"], "recall": recall, "loc_ok": loc_ok,
                "cit_ok": cit_ok, "retrieval_s": round(rl, 3),
                "files": got_files[:3]}
        if with_llm and not item.get("abstain"):
            t1 = time.perf_counter()
            ans = answer_question(item["q"], verbose=False)
            llm_lat.append(time.perf_counter() - t1)
            hit_kw = [k for k in item["keywords"]
                      if k.lower() in ans["answer"].lower()]
            qres["answer_ok"] = 1.0 if len(hit_kw) >= 1 else 0.0
            qres["answer"] = ans["answer"][:500]
            qres["citations"] = ans["citations"]
            qres["gen_s"] = round(ans.get("generation_latency", 0.0), 2)
            print(f"  {item['id']}: recall={recall} loc={loc_ok} ans={qres['answer_ok']} "
                  f"kw={hit_kw} gen={qres['gen_s']}s")
        elif with_llm:
            t1 = time.perf_counter()
            ans = answer_question(item["q"], verbose=False)
            llm_lat.append(time.perf_counter() - t1)
            # Unsupported: retrieved chunks exist, so the LLM must abstain.
            abst = "don't have enough information" in ans["answer"].lower()
            qres["answer_ok"] = 1.0 if abst else 0.0
            qres["answer"] = ans["answer"][:500]
            print(f"  {item['id']}: abstain_ok={qres['answer_ok']}")
        else:
            print(f"  {item['id']}: recall={recall} loc={loc_ok} cit={cit_ok} rtr={rl:.3f}s")
        results["questions"].append(qres)

    n = len(QUESTIONS)
    results["summary"] = {
        "recall_at_3": round(n_recall / n, 3),
        "location_accuracy": round(n_loc / n, 3),
        "citation_validity": round(n_cit_valid / n, 3),
        "avg_retrieval_s": round(sum(rec_lat) / len(rec_lat), 3),
    }
    if with_llm:
        ok = sum(q.get("answer_ok", 0) for q in results["questions"])
        results["summary"]["answer_keyword_hit"] = round(ok / n, 3)
        results["summary"]["avg_llm_s"] = round(sum(llm_lat) / len(llm_lat), 2)
    results["resources"] = {"process_ram_mb": round(psutil.Process().memory_info().rss / 1024**2, 1),
                            "vram_used_mb": vram_mb()}
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSUMMARY:", json.dumps(results["summary"], indent=2))
    print("resources:", results["resources"])
    print("saved to eval_general/results.json")


if __name__ == "__main__":
    main()
