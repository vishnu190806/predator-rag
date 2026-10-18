"""Real-world general-purpose RAG evaluation on genuine public documents.

Corpus: eval_realworld/real_corpus (10 files; provenance in
real_corpus/provenance.json). papers: FAA AC 00-6B (213 pp), FAA AC 107-2A
(104 pp); derived: frankenstein.docx (PG#84), whale_slides.pptx (from the
Wikipedia CC BY-SA article), worldbank.xlsx (WB CC BY-4.0 API snapshot);
real: usgs_jan2024.csv (Jan 2024 M5+ feed), awesome_nodejs.md (CC0),
wcag22.html (W3C), express_package.json (MIT), bluewhale_export.xml
(Wikipedia CC BY-SA).

Question sets are disjoint: CALIB (7, harness sanity only, never reported as
final performance) and HELDOUT (60). Every expected answer/location was taken
from the source documents (see eval_realworld/fact_notes.txt) — locations are
the extractor block labels verified against the real files.

Usage:
  python eval_realworld/eval_realworld.py             # deterministic only
  python eval_realworld/eval_realworld.py --with-llm  # + answer quality
  python eval_realworld/eval_realworld.py --results NAME.json   # output path
Results -> eval_realworld/results.json (or NAME.json).

Harness fix (17 Oct 2026): the held-out pass used to run the LLM regardless
of --with-llm (run_set was called with a hard-coded True), so a "deterministic"
run still spent ~30 min generating. The flag is now honored; TTFT/perf probes
also run only with --with-llm.
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
                    build_context_string, is_empty_answer, EMPTY_ANSWER_MESSAGE)

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "real_corpus")

FILES = ["faa_weather.pdf", "faa_drones.pdf", "frankenstein.docx",
         "whale_slides.pptx", "worldbank.xlsx", "usgs_jan2024.csv",
         "awesome_nodejs.md", "wcag22.html", "express_package.json",
         "bluewhale_export.xml"]

# Note: every keyword below was verified present in the source text (and in
# the extractor block carrying the cited location) by auth_facts.py checks.
HELDOUT = [
    # ---- frankenstein.docx (real public-domain prose, derived container) ----
    {"id": "fr1", "cat": "exact", "q": "In which year was Frankenstein first published?",
     "file": "frankenstein.docx", "loc": "Publication facts",
     "keywords": ["1818"]},
    {"id": "fr2", "cat": "exact", "q": "Whose writings did young Victor become interested in?",
     "file": "frankenstein.docx", "loc": "Chapter 2",
     "keywords": ["Agrippa", "Cornelius"]},
    {"id": "fr3", "cat": "exact", "q": "During which month did the creature come to life?",
     "file": "frankenstein.docx", "loc": "Chapter 5", "keywords": ["November"]},
    {"id": "fr4", "cat": "exact", "q": "How long did Victor work before infusing life into the creature?",
     "file": "frankenstein.docx", "loc": "Chapter 5",
     "any_keywords": ["two years", "two-year", "nearly two"]},
    {"id": "fr5", "cat": "exact", "q": "Which of Victor's family members was murdered, as announced in a letter?",
     "file": "frankenstein.docx", "loc": "Chapter 7", "keywords": ["William"]},
    {"id": "fr6", "cat": "exact", "q": "Who was accused of the murder of Victor's brother?",
     "file": "frankenstein.docx", "loc": None, "keywords": ["Justine"]},
    {"id": "fr7", "cat": "exact", "q": "Where was Walton sailing towards at the start of the narrative?",
     "file": "frankenstein.docx", "loc": "Letter 1",
     "keywords": ["pole", "New World"]},
    # ---- faa_weather.pdf (long real PDF) ----
    {"id": "wx1", "cat": "exact", "q": "What is the standard sea-level pressure in hectopascals?",
     "file": "faa_weather.pdf", "loc": "Page 22", "keywords": ["1013.25"]},
    {"id": "wx2", "cat": "exact", "q": "What is the standard lapse rate of temperature in the troposphere per 1000 meters?",
     "file": "faa_weather.pdf", "loc": "Page 22", "keywords": ["6.5"]},
    {"id": "wx3", "cat": "exact", "q": "How far up does the thermosphere extend?",
     "file": "faa_weather.pdf", "loc": "Page 21", "keywords": ["690"]},
    {"id": "wx4", "cat": "deep", "q": "On average how much ocean water is evaporated into the atmosphere each year?",
     "file": "faa_weather.pdf", "loc": "Page 37", "keywords": ["120"]},
    {"id": "wx5", "cat": "deep", "q": "An air parcel at sea level at 30 degrees Celsius can hold how many grams of water vapor?",
     "file": "faa_weather.pdf", "loc": "Page 38", "keywords": ["27"]},
    {"id": "wx6", "cat": "deep", "q": "How far downwind may mountain waves extend?",
     "file": "faa_weather.pdf", "loc": "Page 156",
     "any_keywords": ["600", "1,000"]},
    {"id": "wx7", "cat": "deep", "q": "How far downwind can ACSL clouds extend?",
     "file": "faa_weather.pdf", "loc": "Page 128",
     "any_keywords": ["60", "100"]},
    # ---- faa_drones.pdf ----
    {"id": "dr1", "cat": "exact", "q": "What is the maximum groundspeed for a small unmanned aircraft?",
     "file": "faa_drones.pdf", "loc": "Page 29",
     "any_keywords": ["87", "100"]},
    {"id": "dr2", "cat": "exact", "q": "How high above ground level may a small unmanned aircraft be flown?",
     "file": "faa_drones.pdf", "loc": "Page 29", "keywords": ["400"]},
    {"id": "dr3", "cat": "exact", "q": "How far away must anti-collision lighting be visible on a small UAS operating at night?",
     "file": "faa_drones.pdf", "loc": "Page 22", "keywords": ["3"]},
    {"id": "dr4", "cat": "exact", "q": "How far below clouds must a small unmanned aircraft remain?",
     "file": "faa_drones.pdf", "loc": "Page 30", "keywords": ["500"]},
    {"id": "dr5", "cat": "exact", "q": "What property repair cost threshold triggers a mandatory accident report?",
     "file": "faa_drones.pdf", "loc": "Page 16", "keywords": ["$500", "500"]},
    {"id": "dr6", "cat": "deep", "q": "Within how many days must a small UAS accident be reported to the FAA?",
     "file": "faa_drones.pdf", "loc": "Page 16",
     "any_keywords": ["10"]},
    # ---- bluewhale_export.xml + whale_slides.pptx (real source + derived deck).
    {"id": "wh1", "cat": "exact", "q": "What is the maximum confirmed length of a blue whale?",
     "file": "bluewhale_export.xml", "loc": None,
     "any_keywords": ["29.9", "30.5"]},
    {"id": "wh2", "cat": "exact", "q": "How long may gestation last for blue whales?",
     "file": "bluewhale_export.xml", "loc": None,
     "any_keywords": ["10–12", "10-12", "10 to 12"]},
    {"id": "wh3", "cat": "exact", "q": "What does the blue whale's diet consist of?",
     "file": "whale_slides.pptx", "loc": "Slide 3", "keywords": ["krill"]},
    {"id": "wh4", "cat": "exact", "q": "How much did the heart of the stranded North Atlantic blue whale weigh?",
     "file": "whale_slides.pptx", "loc": "Slide 2", "keywords": ["180"]},
    {"id": "wh5", "cat": "summary", "q": "List the man-made threats blue whales face.",
     "file": "whale_slides.pptx", "loc": "Slide 5",
     "multi": ["ship strikes", "pollution", "ocean noise", "climate change"],
     "multi_n": 3},
    # ---- worldbank.xlsx (real data, derived multi-sheet workbook) ----
    {"id": "wb1", "cat": "sheetrow", "q": "What was Japan's population in 2022?",
     "file": "worldbank.xlsx", "loc": "Population",
     "keywords": ["125124989"]},
    {"id": "wb2", "cat": "sheetrow", "q": "What was the United Kingdom's population in 2019?",
     "file": "worldbank.xlsx", "loc": "Population",
     "keywords": ["66628000"]},
    {"id": "wb3", "cat": "sheetrow", "q": "What was Germany's population in 2020?",
     "file": "worldbank.xlsx", "loc": "Population",
     "keywords": ["83160871"]},
    {"id": "wb4", "cat": "sheetrow", "q": "What was Brazil's life expectancy in 2021?",
     "file": "worldbank.xlsx", "loc": "Life expectancy",
     "keywords": ["73.038"]},
    {"id": "wb5", "cat": "sheetrow", "q": "What was the United States' life expectancy in 2020?",
     "file": "worldbank.xlsx", "loc": "Life expectancy",
     "any_keywords": ["76.98", "76.980"]},
    {"id": "wb6", "cat": "sheetrow", "q": "What was China's GDP growth rate in 2019?",
     "file": "worldbank.xlsx", "loc": "GDP growth",
     "any_keywords": ["6.067", "6.07", "6.06"]},
    {"id": "wb7", "cat": "conflict", "q": "How did Japan's population change between 2019 and 2023?",
     "file": "worldbank.xlsx", "loc": "Population",
     "multi": ["126633000", "124516650"], "multi_n": 2},
    {"id": "wb8", "cat": "sheetrow",
     "q": "Calculate how much Japan's population changed from 2019 to 2023.",
     "file": "worldbank.xlsx", "loc": "Population",
     "multi": ["126633000", "124516650"], "multi_n": 1,
     "note": "'Calculate' routes this to the numerical prompt/budget path"},
    # ---- usgs_jan2024.csv (real feed snapshot) ----
    {"id": "eq1", "cat": "sheetrow", "q": "What was the magnitude of earthquake id us6000m0xl?",
     "file": "usgs_jan2024.csv", "loc": "rows 132", "keywords": ["7.5"]},
    {"id": "eq2", "cat": "sheetrow", "q": "How deep was earthquake id us7000lsze?",
     "file": "usgs_jan2024.csv", "loc": "rows 49", "keywords": ["13"]},
    {"id": "eq3", "cat": "sheetrow", "q": "How deep was earthquake id us6000m52p?",
     "file": "usgs_jan2024.csv", "loc": "rows 55", "keywords": ["607"]},
    {"id": "eq4", "cat": "sheetrow", "q": "What was the magnitude of earthquake id us7000lui3?",
     "file": "usgs_jan2024.csv", "loc": "rows 7", "keywords": ["6.5"]},
    {"id": "eq5", "cat": "sheetrow", "q": "Where did earthquake id us6000m2jp occur?",
     "file": "usgs_jan2024.csv", "loc": "rows 98",
     "keywords": ["Sarangani", "Philippines"]},
    # ---- awesome_nodejs.md (real CC0 readme) ----
    {"id": "md1", "cat": "identifier", "q": "Under which awesome-nodejs section is the webtorrent project listed?",
     "file": "awesome_nodejs.md", "loc": "Mad science",
     "keywords": ["Mad science"]},
    {"id": "md2", "cat": "identifier", "q": "Under which awesome-nodejs section is chalk listed?",
     "file": "awesome_nodejs.md", "loc": "Command-line utilities",
     "keywords": ["Command-line utilities", "utilities"]},
    {"id": "md3", "cat": "identifier", "q": "Which HTTP client libraries does awesome-nodejs list?",
     "file": "awesome_nodejs.md", "loc": "HTTP",
     "multi": ["got", "axios", "node-fetch", "undici", "ky-universal"],
     "multi_n": 2},
    # ---- wcag22.html (real W3C spec) ----
    {"id": "wc1", "cat": "exact", "q": "What minimum contrast ratio does WCAG require for normal text at Level AA?",
     "file": "wcag22.html", "loc": "1.4.3", "keywords": ["4.5:1"]},
    {"id": "wc2", "cat": "exact", "q": "What minimum contrast ratio does WCAG require at Level AAA?",
     "file": "wcag22.html", "loc": "1.4.6", "keywords": ["7:1"]},
    {"id": "wc3", "cat": "exact", "q": "What minimum contrast ratio applies to large-scale text at Level AA?",
     "file": "wcag22.html", "loc": "1.4.3", "keywords": ["3:1"]},
    {"id": "wc4", "cat": "exact", "q": "What is the minimum target size for pointer inputs in WCAG 2.2?",
     "file": "wcag22.html", "loc": "2.5.8",
     "keywords": ["24 by 24", "24 CSS pixels"]},
    {"id": "wc5", "cat": "exact", "q": "For how long may moving or blinking information start automatically on a page per WCAG?",
     "file": "wcag22.html", "loc": "2.2.2",
     "keywords": ["five seconds", "5 seconds"]},
    # ---- express_package.json (real MIT manifest) ----
    {"id": "js1", "cat": "identifier", "q": "What minimum Node version does the express package require?",
     "file": "express_package.json", "loc": None, "keywords": ["18"]},
    {"id": "js2", "cat": "identifier", "q": "What license is the express package distributed under?",
     "file": "express_package.json", "loc": None, "keywords": ["MIT"]},
    {"id": "js3", "cat": "identifier", "q": "What is the version of the cookie dependency in express?",
     "file": "express_package.json", "loc": None, "keywords": ["0.7.1"]},
    # ---- similar entities / distractors ----
    {"id": "sm1", "cat": "similar", "q": "How heavy can the largest blue whale get (maximum, not the average)?",
     "file": "whale_slides.pptx", "loc": "Slide 2",
     "keywords": ["190–200", "190-200", "200 t"]},
    {"id": "sm2", "cat": "similar", "q": "What is the average adult blue whale weight?",
     "file": "whale_slides.pptx", "loc": "Slide 2",
     "any_keywords": ["72–135", "72-135"]},
    {"id": "sm3", "cat": "similar", "q": "Which had higher GDP growth in 2020, China or India?",
     "file": "worldbank.xlsx", "loc": "GDP growth",
     "any_keywords": ["China", "2.339"]},
    # ---- cross-document ----
    {"id": "cd1", "cat": "crossdoc", "q": "What is the header publication date of AC 00-6B and of AC 107-2A?",
     "file": None, "loc": None,
     "files_all": ["faa_weather.pdf", "faa_drones.pdf"],
     "multi": ["8/23/16", "2/1/21"], "multi_n": 2},
    {"id": "cd2", "cat": "crossdoc", "q": "How much does a blue whale's heart weigh according to the fact sheet and the Wikipedia article?",
     "file": None, "loc": None,
     "files_all": ["whale_slides.pptx", "bluewhale_export.xml"],
     "keywords": ["180"]},
    # ---- summaries over several passages ----
    {"id": "su1", "cat": "summary", "q": "What happened to Justine after the trial, in Frankenstein?",
     "file": "frankenstein.docx", "loc": None,
     "any_keywords": ["confess", "died", "William", "Elizabeth", "condemned"]},
    {"id": "su2", "cat": "summary", "q": "Summarize the operating limitations for small unmanned aircraft.",
     "file": "faa_drones.pdf", "loc": None,
     "multi": ["87", "400", "500"], "multi_n": 2},
    # ---- absent answers (must abstain) ----
    {"id": "ab1", "cat": "absent", "q": "What is the capital city of Australia?",
     "abstain": True},
    {"id": "ab2", "cat": "absent", "q": "What is the boiling point of helium?",
     "abstain": True},
    {"id": "ab3", "cat": "absent", "q": "What was France's population in 1950?",
     "abstain": True},
    {"id": "ab4", "cat": "absent", "q": "According to Frankenstein, how many languages did the creature learn?",
     "abstain": True},
]

CALIB = [
    {"id": "c1", "q": "Who is the author of Frankenstein?",
     "file": "frankenstein.docx", "loc": "Publication facts",
     "keywords": ["Shelley", "Mary"]},
    {"id": "c2", "q": "What temperature can the top of the thermosphere reach?",
     "file": "faa_weather.pdf", "loc": "Page 21", "keywords": ["2,000"]},
    {"id": "c3", "q": "How far must a small unmanned aircraft stay horizontally from clouds?",
     "file": "faa_drones.pdf", "loc": "Page 30", "keywords": ["2,000"]},
    {"id": "c4", "q": "How many blue whales were killed or injured along the California coast per the fact sheet note?",
     "file": "whale_slides.pptx", "loc": "Slide 5", "keywords": ["17"]},
    {"id": "c5", "q": "Which AVA-hosted testing framework is listed under Testing in awesome-nodejs?",
     "file": "awesome_nodejs.md", "loc": "Testing", "keywords": ["AVA"]},
    {"id": "c6", "q": "What happens to relative humidity when the spread decreases to zero?",
     "file": "faa_weather.pdf", "loc": "Page 39", "keywords": ["100"]},
    {"id": "c7", "q": "What is the status given to blue whales by the IUCN?",
     "file": "whale_slides.pptx", "loc": "Slide 4", "keywords": ["endangered"]},
    {"id": "c8", "q": "What is the elevation of Mount Nemo?", "abstain": True},
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
        return ("don't have enough information" in t or
                "not able to answer" in t or
                "cannot answer" in t), ["refusal"]
    if "absent" in item and any(a.lower() in t for a in item["absent"]):
        return False, ["ABSENT-VIOLATION"]
    if "multi" in item:
        hits = [k for k in item["multi"] if k.lower() in t]
        return (len(hits) >= item.get("multi_n", 2)), hits
    pool = item.get("keywords", []) + item.get("any_keywords", [])
    hits = [k for k in pool if k.lower() in t]
    return (len(hits) >= 1), hits


def main():
    with_llm = "--with-llm" in sys.argv
    results_name = "results.json"
    if "--results" in sys.argv:
        results_name = sys.argv[sys.argv.index("--results") + 1]
    results_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                results_name)
    tmp = os.path.join(HERE, "tmp_real")
    chroma = os.path.join(tmp, "chroma")
    cache = os.path.join(tmp, "cache")
    os.makedirs(chroma, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    ingest.CHROMA_DB_PATH = chroma
    ingest.EMBED_CACHE_DIR = cache
    retrieve.CHROMA_DB_PATH = chroma
    resume = "--resume" in sys.argv
    res = {"extraction": {}, "index": {}, "calib": [], "heldout": [], "perf": {}}
    if resume and os.path.exists(results_path):
        try:
            with open(results_path, encoding="utf-8") as f:
                _prev = json.load(f)
            res["extraction"] = _prev.get("extraction", {})
            res["index"] = _prev.get("index", {})
            res["calib"] = _prev.get("calib", [])
            res["heldout"] = _prev.get("heldout", [])
            print("RESUME: loaded", len(res["heldout"]), "heldout results")
        except Exception as e:
            print("RESUME load failed:", e)

    # ---- extraction ----------------------------------------------------------
    for fname in FILES:
        t0 = time.perf_counter()
        dt, blocks = extractors.extract_file(os.path.join(CORPUS, fname))
        el = time.perf_counter() - t0
        res["extraction"][fname] = {"s": round(el, 3), "blocks": len(blocks)}
        print(f"extract {fname}: {el:.3f}s {len(blocks)} blocks")

    # ---- ingestion: cold, then cache-hit timing (no DB writes) ---------------
    t0 = time.perf_counter()
    total = 0
    for i, fname in enumerate(FILES):
        total += ingest.ingest_file(os.path.join(CORPUS, fname),
                                    recreate=(i == 0),
                                    original_filename=fname)
    cold = time.perf_counter() - t0
    with open(os.path.join(CORPUS, FILES[0]), "rb") as f:
        hot_bytes = f.read()
    from ingest import _embed_chunks_cached, make_chunk_records
    dt, blocks = extractors.extract_file(os.path.join(CORPUS, FILES[0]))
    recs = make_chunk_records(blocks, FILES[0], "pdf",
                              "realtiming-" + FILES[0])
    t0 = time.perf_counter()
    _embed_chunks_cached(hot_bytes, FILES[0], recs)
    hot = time.perf_counter() - t0
    res["index"] = {"cold_s": round(cold, 2), "cache_hit_s": round(hot, 2),
                    "chunks_total": total}
    print(f"index cold {cold:.2f}s ({total} chunks), cache-hit {hot:.2f}s")

    retrieve.initialize_retrieval_components()
    n_files = len(FILES)
    docs = ingest.list_documents()
    assert set(docs) <= set(FILES) and len(docs) == n_files, docs
    print(f"workspace: {sorted(docs)}")

    # ---- question loop -------------------------------------------------------
    def run_set(questions, store, with_llm_flag):
        rec_lat = []
        for item in questions:
            if any(x.get("id") == item["id"] for x in store):
                t0 = time.perf_counter()
                retrieve.retrieve(item["q"], limit=3)
                rec_lat.append(time.perf_counter() - t0)
                print(f"  {item['id']} [skip: already done]")
                continue
            t0 = time.perf_counter()
            hits = retrieve.retrieve(item["q"], limit=3)
            rl = time.perf_counter() - t0
            rec_lat.append(rl)
            hits6 = retrieve.retrieve(item["q"], limit=6)
            files3 = [h["metadata"]["file"] for h in hits]
            files6 = [h["metadata"]["file"] for h in hits6]
            accepted = item.get("file") or item.get("files_all")
            if accepted:
                need = item.get("files_all", [item.get("file")])
                r3 = 1.0 if (item.get("files_all") and
                             all(f in files6 for f in need)) or \
                    (not item.get("files_all") and
                     item["file"] in files3) else 0.0
                r6 = 1.0 if all(f in files6 for f in need) else 0.0
            else:
                r3 = 1.0
                r6 = 1.0
            if item.get("loc") and r3:
                loc = 1.0 if any(item["loc"].lower() in
                                 location_label(h["metadata"]).lower()
                                 for h in hits
                                 if h["metadata"]["file"] ==
                                 (item.get("file") or files3[0])) else 0.0
            else:
                loc = 1.0
            cits = format_citations(hits)
            cit_ok = 1.0 if cits else 0.0
            qres = {"id": item["id"], "cat": item.get("cat", "calib"),
                    "q": item["q"], "recall3": r3, "recall6": r6,
                    "loc": loc, "cit": cit_ok, "files3": files3,
                    "rtr_s": round(rl, 3)}
            if with_llm_flag and not item.get("abstain"):
                t1 = time.perf_counter()
                attempts = 1
                try:
                    ans = answer_question(item["q"], verbose=False)
                except Exception as exc:  # request-level failure (timeout etc.)
                    ans = {"answer": f"REQUEST_ERROR: {type(exc).__name__}: {exc}",
                           "citations": [], "generation_latency": -1.0,
                           "error_kind": type(exc).__name__}
                if ans["answer"].startswith("REQUEST_ERROR") or \
                        is_empty_answer(ans["answer"]):
                    attempts = 2  # one automatic retry, as a human would in the app
                    try:
                        ans = answer_question(item["q"], verbose=False)
                    except Exception as exc:
                        ans = {"answer":
                               f"REQUEST_ERROR: {type(exc).__name__}: {exc}",
                               "citations": [], "generation_latency": -1.0,
                               "error_kind": type(exc).__name__}
                gen = time.perf_counter() - t1
                ok, kw = check_answer(item, ans["answer"])
                empty = is_empty_answer(ans["answer"])
                qres.update({"ans": 1.0 if ok else 0.0, "kw": kw,
                             "gen_s": round(ans.get("generation_latency", gen),
                                            2),
                             "answer": ans["answer"][:700],
                             "citations": ans["citations"],
                             "empty": bool(empty), "attempts": attempts})
                print(f"  {item['id']} [{qres['cat']}]: r3={r3} l={loc} "
                      f"a={qres['ans']} {kw} gen={qres['gen_s']}s")
            elif with_llm_flag and item.get("abstain"):
                t1 = time.perf_counter()
                try:
                    ans = answer_question(item["q"], verbose=False)
                except Exception as exc:
                    ans = {"answer": f"REQUEST_ERROR: {type(exc).__name__}: {exc}",
                           "citations": [], "generation_latency": -1.0,
                           "error_kind": type(exc).__name__}
                gen = time.perf_counter() - t1
                ok, kw = check_answer(item, ans["answer"])
                qres.update({"ans": 1.0 if ok else 0.0, "kw": kw,
                             "gen_s": round(ans.get("generation_latency", gen),
                                            2),
                             "answer": ans["answer"][:400],
                             "empty": is_empty_answer(ans["answer"])})
                print(f"  {item['id']} [abstain]: a={qres['ans']} "
                      f"(kw={kw}) gen={qres['gen_s']}s")
            else:
                print(f"  {item['id']} [{qres['cat']}]: r3={r3} r6={r6} "
                      f"l={loc} c={cit_ok} rtr={rl:.3f}s")
            store.append(qres)
            with open(results_path, "w",
                      encoding="utf-8") as f:
                json.dump(res, f, indent=2)  # incremental dump: survives kills
            if not with_llm_flag:
                del qres["files3"]
        return rec_lat

    run_set(CALIB, res["calib"], False)          # deterministic sanity only
    lat = run_set(HELDOUT, res["heldout"], with_llm)  # LLM only with --with-llm

    # per-category summary on the HELDOUT set
    cats = {}
    for q in res["heldout"]:
        cats.setdefault(q["cat"], []).append(q)
    summary = {"n": len(HELDOUT)}
    for fld in ["recall3", "recall6", "loc", "cit", "ans"]:
        summary[fld] = round(sum(q.get(fld, 0) for q in res["heldout"]) /
                             len(HELDOUT), 3)
    summary["by_cat"] = {c: {"n": len(v),
                             "recall3": round(sum(x["recall3"] for x in v) /
                                              len(v), 3),
                             "recall6": round(sum(x["recall6"] for x in v) /
                                              len(v), 3),
                             "loc": round(sum(x["loc"] for x in v) /
                                          len(v), 3),
                             "ans": round(sum(x.get("ans", 0) for x in v) /
                                          len(v), 3)}
                         for c, v in cats.items()}
    res["summary"] = summary
    print("\nSUMMARY:", json.dumps(summary, indent=1))

    # ---- perf: medians + TTFT (TTFT needs the LLM) ----------------------------
    srt = sorted(lat)
    res["perf"]["retrieval_median_s"] = round(statistics.median(lat), 3)
    res["perf"]["retrieval_p95_s"] = round(
        srt[min(len(srt) - 1, int(len(srt) * 0.95))], 3)
    ttfts = []
    if with_llm:
        for qid in ["fr3", "wb1", "wc1"]:
            item = next(i for i in HELDOUT if i["id"] == qid)
            hits = retrieve.retrieve(item["q"], limit=6)
            ctx = build_context_string(hits)
            t0 = time.perf_counter()
            for tok in generate_answer_stream(item["q"], ctx,
                                              is_numerical_question(item["q"])):
                if tok:
                    ttfts.append(round(time.perf_counter() - t0, 2))
                    break
    res["perf"]["ttft_s"] = ttfts
    res["resources"] = {
        "process_ram_mb": round(psutil.Process().memory_info().rss / 1024**2, 1),
        "vram_mb": vram_mb()}
    res["reliability"] = {
        "empty_answers": sum(1 for q in res["heldout"] if q.get("empty")),
        "request_errors": sum(1 for q in res["heldout"]
                              if str(q.get("answer", "")).startswith("REQUEST_ERROR")),
        "auto_retries": sum(1 for q in res["heldout"] if q.get("attempts", 1) > 1),
        "generations": sum(1 for q in res["heldout"] if "gen_s" in q)}
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print("perf:", res["perf"], "resources:", res["resources"],
          "reliability:", res["reliability"])


if __name__ == "__main__":
    main()
