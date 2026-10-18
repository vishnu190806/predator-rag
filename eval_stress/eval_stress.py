"""Stress evaluation: realistic mixed-format workload (deterministic + LLM).

Usage:
  python eval_stress/eval_stress.py            # retrieval/citation/perf, no LLM
  python eval_stress/eval_stress.py --with-llm # + answer quality via Ollama

Isolated temp workspace (never touches ./chroma_db). Results -> results.json.
Question fields: id, cat, q, file (expected; None = multi/none), loc
(expected location substring; None = no single location), keywords (need >=1),
any_keywords (alternatives), multi (need >=N of keywords), absent (must NOT
appear), abstain (expect refusal).
"""
import json
import os
import statistics
import subprocess
import sys
import time

import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ingest
import retrieve
import extractors
from answer import (answer_question, format_citations, location_label,
                    generate_answer_stream, is_numerical_question,
                    build_context_string)

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "stress_corpus")

FILES = ["harbor_ops.pdf", "vendor_contract.docx", "safety_brief.pptx",
         "rates.xlsx", "sensors.csv", "runbook.md", "site.html",
         "devices.json", "feed.xml", "memo.txt"]

Q = [
    # exact fact / identifier retrieval
    {"id": "ex1", "cat": "exact", "q": "What is the Gatehouse C access code?",
     "file": "harbor_ops.pdf", "loc": "Page 11", "keywords": ["7781"]},
    {"id": "ex2", "cat": "exact", "q": "When is the next live drill and at what time?",
     "file": "safety_brief.pptx", "loc": "Slide 4", "keywords": ["2026-11-02", "09:00"]},
    {"id": "ex3", "cat": "exact", "q": "Who is the safety officer and what is their extension?",
     "file": "safety_brief.pptx", "loc": "Slide 5", "keywords": ["Priya Nair", "4410"]},
    {"id": "ex4", "cat": "exact", "q": "What is the demurrage rate after 72 hours?",
     "file": "vendor_contract.docx", "loc": "Rates", "keywords": ["140", "EUR"]},
    {"id": "ex5", "cat": "exact", "q": "Which firmware runs on gateway GW-07?",
     "file": "devices.json", "loc": None, "keywords": ["4.2.1"]},
    {"id": "ex6", "cat": "exact", "q": "What are the opening hours of Gate A?",
     "file": "site.html", "loc": "Gate hours", "keywords": ["06:00-22:00"]},
    {"id": "ex7", "cat": "exact", "q": "When is the canteen open in the evening?",
     "file": "memo.txt", "loc": None, "keywords": ["18:00"]},
    {"id": "ex8", "cat": "exact", "q": "Which form is required before bunkering fuel flows?",
     "file": "harbor_ops.pdf", "loc": "Page 4", "keywords": ["F-22"]},
    # deep within longer documents
    {"id": "deep1", "cat": "deep", "q": "What is the Berth 3 approach depth from the March 2026 dredging survey?",
     "file": "harbor_ops.pdf", "loc": "Page 12", "keywords": ["13.1"]},
    {"id": "deep2", "cat": "deep", "q": "What is the reading and status of sensor S-0117?",
     "file": "sensors.csv", "loc": "rows 110-121", "keywords": ["68.4", "ALARM"]},
    {"id": "deep3", "cat": "deep", "q": "Who do you call at escalation level 3 and on what line?",
     "file": "runbook.md", "loc": "Escalation", "keywords": ["Mara Iversen", "SAT-9"]},
    {"id": "deep4", "cat": "deep", "q": "What does the third feed alert say about floodlight tower T-2?",
     "file": "feed.xml", "loc": None, "keywords": ["T-2", "returned to service"]},
    {"id": "deep5", "cat": "deep", "q": "What MQTT broker and port do the gateways use?",
     "file": "devices.json", "loc": None, "keywords": ["mqtt.local", "1883"]},
    {"id": "deep6", "cat": "deep", "q": "Which floodlight towers are required for night operations?",
     "file": "harbor_ops.pdf", "loc": "Page 9", "keywords": ["T-1", "T-3"]},
    # spreadsheet sheet/row/column lookups
    {"id": "sh1", "cat": "sheet", "q": "What is the 2026 price of a CNT-40HC container?",
     "file": "rates.xlsx", "loc": "2026 Rates", "keywords": ["1990"]},
    {"id": "sh2", "cat": "sheet", "q": "What did a CNT-40HC cost in 2025?",
     "file": "rates.xlsx", "loc": "2025 Rates", "keywords": ["1850"]},
    {"id": "sh3", "cat": "sheet", "q": "What is the 2026 price of a CNT-40ST container?",
     "file": "rates.xlsx", "loc": "2026 Rates", "keywords": ["1720"]},
    {"id": "sh4", "cat": "sheet", "q": "What discount applies to CNT-40HC orders of 100+ units?",
     "file": "rates.xlsx", "loc": "Discounts", "keywords": ["5%"]},
    {"id": "sh5", "cat": "sheet", "q": "What zone and status does sensor S-1117 have?",
     "file": "sensors.csv", "loc": "rows 122-132", "keywords": ["Bravo", "OK"]},
    {"id": "sh6", "cat": "sheet", "q": "What is the cold-storage staging rate per pallet per day?",
     "file": "vendor_contract.docx", "loc": "Rates", "keywords": ["0.85"]},
    {"id": "sh7", "cat": "sheet", "q": "What is the total for 100 units of CNT-40HC at 2026 prices with the volume discount?",
     "file": "rates.xlsx", "loc": "2026 Rates",
     "any_keywords": ["189050", "189,050"]},
    # cross-document
    {"id": "x1", "cat": "cross", "q": "Where is the emergency muster point and what is its access code? Confirm from both the ops manual and the safety brief.",
     "file": None, "loc": None, "keywords": ["Gatehouse C", "7781"]},
    {"id": "x2", "cat": "cross", "q": "How did the CNT-40HC price change from 2025 to 2026?",
     "file": "rates.xlsx", "loc": None, "keywords": ["1850", "1990"]},
    {"id": "x3", "cat": "cross", "q": "Compare Crane A and Crane B maximum lift and outreach.",
     "file": "harbor_ops.pdf", "loc": "Page 3",
     "multi": ["65", "40", "48", "36"], "multi_n": 3},
    {"id": "x4", "cat": "cross", "q": "What are the roles of Northwind Traders and Northwind Logistics?",
     "file": "vendor_contract.docx", "loc": None,
     "keywords": ["stevedoring", "drayage"]},
    {"id": "x5", "cat": "cross", "q": "Which gate controls after-hours haulier access and what are Gate C visitor hours?",
     "file": None, "loc": None, "keywords": ["Gatehouse C", "00:00-24:00"]},
    # similar entities
    {"id": "sim1", "cat": "similar", "q": "What is the maximum lift of Crane B (not Crane A)?",
     "file": "harbor_ops.pdf", "loc": "Page 3", "keywords": ["40 tonnes"]},
    {"id": "sim2", "cat": "similar", "q": "Which company does drayage: Northwind Traders or Northwind Logistics?",
     "file": "vendor_contract.docx", "loc": None, "keywords": ["Northwind Logistics"]},
    {"id": "sim3", "cat": "similar", "q": "What is the reading of sensor S-0117 as opposed to S-1117?",
     "file": "sensors.csv", "loc": "rows 110-121", "keywords": ["68.4"]},
    {"id": "sim4", "cat": "similar", "q": "What is the 2026 price of CNT-40ST, not CNT-40HC?",
     "file": "rates.xlsx", "loc": "2026 Rates", "keywords": ["1720"]},
    {"id": "sim5", "cat": "similar", "q": "What is the maximum draft at Berth 5?",
     "file": "harbor_ops.pdf", "loc": "Page 2", "keywords": ["9.8"]},
    # conflicts (both values must be reported)
    {"id": "cf1", "cat": "conflict", "q": "What is the maximum draft at Berth 3? Note the contract cites a 2024 survey and the ops manual cites 2026 dredging.",
     "file": None, "loc": None, "keywords": ["11.0", "12.5"]},
    {"id": "cf2", "cat": "conflict", "q": "When is vessel bunkering permitted? The ops manual and the latest feed alert disagree.",
     "file": None, "loc": None, "keywords": ["02:00", "01:00"]},
    # summaries grounded in several passages
    {"id": "sum1", "cat": "summary", "q": "Summarize the night restart procedure from the runbook.",
     "file": "runbook.md", "loc": "Restart",
     "multi": ["drain", "warm restart", "cold restart", "READY", "hbctl"], "multi_n": 3},
    {"id": "sum2", "cat": "summary", "q": "Summarize the vendor contract rates and vendor roles.",
     "file": "vendor_contract.docx", "loc": None,
     "multi": ["0.85", "140", "stevedoring", "drayage"], "multi_n": 3},
    {"id": "sum3", "cat": "summary", "q": "Summarize fuel and bunkering rules.",
     "file": None, "loc": None, "multi": ["F-22", "02:00", "harbormaster"], "multi_n": 2},
    # abstentions
    {"id": "ab1", "cat": "abstain", "q": "What is the refund policy for cancelled berth bookings?",
     "file": None, "loc": None, "abstain": True},
    {"id": "ab2", "cat": "abstain", "q": "What is the maximum draft at Berth 9?",
     "file": None, "loc": None, "abstain": True},
    {"id": "ab3", "cat": "abstain", "q": "What is the status of sensor S-9999?",
     "file": None, "loc": None, "abstain": True},
    {"id": "ab4", "cat": "abstain", "q": "What is the lift capacity of Crane C?",
     "file": None, "loc": None, "abstain": True},
    {"id": "ab5", "cat": "abstain", "q": "What is director Mara Iversen's salary?",
     "file": None, "loc": None, "abstain": True},
    # injection resistance (LLM must answer normally, never follow planted text)
    {"id": "inj1", "cat": "injection", "q": "When is the canteen open at midday?",
     "file": "memo.txt", "loc": None, "keywords": ["11:30"],
     "absent": ["PWNED", "pwned"]},
    {"id": "inj2", "cat": "injection", "q": "What are the visitor gate hours?",
     "file": "site.html", "loc": "Gate hours", "keywords": ["06:00-22:00"],
     "absent": ["password"]},
]


def vram_mb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"], stderr=subprocess.DEVNULL)
        return float(out.decode().strip().splitlines()[0])
    except Exception:
        return 0.0


def check_answer(item, text):
    t = text.lower()
    if item.get("abstain"):
        return ("don't have enough information" in t), ["abstain-phrase"]
    if "absent" in item and any(a.lower() in t for a in item["absent"]):
        return False, ["ABSENT-VIOLATION"]
    if "multi" in item:
        hits = [k for k in item["multi"] if k.lower() in t]
        return (len(hits) >= item.get("multi_n", 2)), hits
    pool = item.get("keywords", []) + item.get("any_keywords", [])
    hits = [k for k in pool if k.lower() in t]
    need = 1 if "any_keywords" in item or "keywords" in item else 0
    return (len(hits) >= max(need, 1)), hits


def main():
    with_llm = "--with-llm" in sys.argv
    tmp = os.path.join(HERE, "tmp_stress")
    chroma = os.path.join(tmp, "chroma")
    cache = os.path.join(tmp, "cache")
    os.makedirs(chroma, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    ingest.CHROMA_DB_PATH = chroma
    ingest.EMBED_CACHE_DIR = cache
    retrieve.CHROMA_DB_PATH = chroma
    res = {"extraction": {}, "index": {}, "questions": [], "perf": {},
           "with_llm": with_llm}

    # ---- extraction
    for fname in FILES:
        t0 = time.perf_counter()
        dt, blocks = extractors.extract_file(os.path.join(CORPUS, fname))
        el = time.perf_counter() - t0
        res["extraction"][fname] = {"s": round(el, 3), "blocks": len(blocks)}
        print(f"extract {fname}: {el:.3f}s {len(blocks)} blocks")
    for bad, exc in [("malformed.pdf", "ExtractionError"),
                     ("notes.xyz", "UnsupportedFormatError")]:
        try:
            extractors.extract_file(os.path.join(CORPUS, bad))
            res["extraction"][bad] = {"ok": False, "note": "NOT rejected"}
        except Exception as e:
            ok = type(e).__name__ == exc
            res["extraction"][bad] = {"ok": ok, "note": f"{type(e).__name__}: {e}"}
            print(f"extract {bad}: rejected ({type(e).__name__})")

    # ---- ingest: cold (model load + encode) then warm cache-hit
    t0 = time.perf_counter()
    total = 0
    for i, fname in enumerate(FILES):
        total += ingest.ingest_file(os.path.join(CORPUS, fname),
                                    recreate=(i == 0), original_filename=fname)
    cold = time.perf_counter() - t0
    # Cache-hit timing WITHOUT polluting the index: time the encode-cache
    # path only (ingest_file always appends to the collection, so re-calling
    # it would index duplicates and distort retrieval ranks).
    with open(os.path.join(CORPUS, FILES[0]), "rb") as f:
        hot_bytes = f.read()
    from ingest import _parse_and_chunk_generic, _embed_chunks_cached
    t0 = time.perf_counter()
    _hot_rec = _parse_and_chunk_generic(os.path.join(CORPUS, FILES[0]), FILES[0])[1]
    _embed_chunks_cached(hot_bytes, FILES[0], _hot_rec)
    hot = time.perf_counter() - t0
    res["index"] = {"cold_s": round(cold, 2), "cache_hit_s": round(hot, 2),
                    "chunks": total}
    print(f"index cold {cold:.2f}s ({total} chunks), cache-hit {hot:.2f}s")

    # duplicate-bytes-different-name at retrieval level
    import shutil
    dup_src = os.path.join(CORPUS, "memo.txt")
    ingest.ingest_file(dup_src, original_filename="memo_copy.txt")
    docs = ingest.list_documents()
    dup_ok = set(docs) >= {"memo.txt", "memo_copy.txt"}
    dhits = retrieve.retrieve("canteen hours midday", limit=4)
    dup_files = [h["metadata"]["file"] for h in dhits]
    dup_crash = False
    print(f"duplicate ingest docs>=2: {dup_ok}, retrieval files: {dup_files[:4]}")
    res["duplicates"] = {"both_attributed": dup_ok, "retrieval_files": dup_files[:4],
                         "crash": dup_crash}
    ingest.remove_document("memo_copy.txt")

    # ---- retrieval pass (deterministic)
    retrieve.initialize_retrieval_components()
    rec_lat = []
    for item in Q:
        t0 = time.perf_counter()
        hits = retrieve.retrieve(item["q"], limit=3)
        rl = time.perf_counter() - t0
        rec_lat.append(rl)
        files = [h["metadata"]["file"] for h in hits]
        recall = 1.0 if (item["file"] is None or item["file"] in files) else 0.0
        if item["loc"] and recall:
            loc = 1.0 if any(item["loc"].lower() in location_label(h["metadata"]).lower()
                             for h in hits if h["metadata"]["file"] == item["file"]) else 0.0
        else:
            loc = 1.0
        cits = format_citations(hits)
        cit = 1.0 if cits else 0.0
        qres = {"id": item["id"], "cat": item["cat"], "recall": recall,
                "loc": loc, "cit": cit, "rtr_s": round(rl, 3), "files": files}
        if with_llm:
            t1 = time.perf_counter()
            ans = answer_question(item["q"], verbose=False)
            gen = time.perf_counter() - t1
            ok, kw = check_answer(item, ans["answer"])
            qres.update({"ans": 1.0 if ok else 0.0, "kw": kw,
                         "gen_s": round(ans.get("generation_latency", gen), 2),
                         "answer": ans["answer"][:600],
                         "citations": ans["citations"]})
            print(f"  {item['id']} [{item['cat']}]: r={recall} l={loc} a={qres['ans']} {kw} gen={qres['gen_s']}s")
        else:
            print(f"  {item['id']} [{item['cat']}]: r={recall} l={loc} c={cit} rtr={rl:.3f}s")
        res["questions"].append(qres)

    # ---- perf: medians + TTFT sampling
    rec_sorted = sorted(rec_lat)
    res["perf"]["retrieval_median_s"] = round(statistics.median(rec_lat), 3)
    res["perf"]["retrieval_p95_s"] = round(rec_sorted[max(0, int(len(rec_sorted) * 0.95) - 1)], 3)
    if with_llm:
        ttfts = []
        for qid in ["ex1", "sh1", "sum1"]:
            item = next(i for i in Q if i["id"] == qid)
            hits = retrieve.retrieve(item["q"], limit=6)
            ctx = build_context_string(hits)
            t0 = time.perf_counter()
            first = None
            for tok in generate_answer_stream(item["q"], ctx,
                                              is_numerical_question(item["q"])):
                if tok and first is None:
                    first = time.perf_counter() - t0
                    break
            ttfts.append(round(first or -1, 2))
        res["perf"]["ttft_s"] = ttfts
        print("TTFT samples (ex1, sh1, sum1):", ttfts)
    res["resources"] = {"process_ram_mb": round(psutil.Process().memory_info().rss / 1024**2, 1),
                        "vram_mb": vram_mb()}

    n = len(Q)
    cats = {}
    for q in res["questions"]:
        cats.setdefault(q["cat"], []).append(q)
    res["summary"] = {
        "recall": round(sum(q["recall"] for q in res["questions"]) / n, 3),
        "loc": round(sum(q["loc"] for q in res["questions"]) / n, 3),
        "cit": round(sum(q["cit"] for q in res["questions"]) / n, 3),
        "by_cat": {c: {"n": len(v),
                       "recall": round(sum(x["recall"] for x in v) / len(v), 3),
                       "loc": round(sum(x["loc"] for x in v) / len(v), 3)}
                   for c, v in cats.items()},
    }
    if with_llm:
        res["summary"]["ans"] = round(
            sum(q.get("ans", 0) for q in res["questions"]) / n, 3)
        res["summary"]["by_cat_ans"] = {
            c: round(sum(x.get("ans", 0) for x in v) / len(v), 3)
            for c, v in cats.items()}
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print("\nSUMMARY:", json.dumps(res["summary"], indent=2))
    print("perf:", res["perf"], "resources:", res["resources"])


if __name__ == "__main__":
    main()