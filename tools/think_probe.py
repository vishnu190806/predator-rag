"""Follow-up: (a) full-answer capture for manual verification of key qwen3 wins;
(b) qwen3:8b think:false arm to isolate the thinking latency/accuracy effect.
Same frozen-context method, same templates/caps/ctx, same grader.
Writes: think_probe_results.json (full answer texts included).
"""
import json, os, shutil, sys, time
sys.stdout.reconfigure(encoding="utf-8")

TMP_DB = "./chroma_thinkprobe"
if os.path.exists(TMP_DB):
    shutil.rmtree(TMP_DB)

import ingest as I
import retrieve as R
I.CHROMA_DB_PATH = TMP_DB
R.CHROMA_DB_PATH = TMP_DB

import chromadb
client = chromadb.PersistentClient(path=TMP_DB)
coll = client.get_or_create_collection(R.COLLECTION_NAME)
at, ae, am = [], [], []
for pdf in ["data/keph105.pdf", "data/keph106.pdf", "data/keph107.pdf"]:
    pb, chunks = I._parse_and_chunk_pdf(pdf, os.path.basename(pdf))
    t, e, m = I._embed_chunks_cached(pb, os.path.basename(pdf), chunks)
    at.extend(t); ae.extend(e); am.extend(m)
I._add_to_collection(coll, at, ae, am)
R.initialize_retrieval_components()

import requests
from answer import (build_context_string, is_numerical_question, OLLAMA_HOST,
                    NUM_CTX, THEORY_PROMPT_TEMPLATE, NUMERICAL_PROMPT_TEMPLATE)
from benchmark import grade_answer_llm

bench = json.load(open("benchmark_questions.json", encoding="utf-8"))
by_id = {q["id"]: q for q in bench}

def gen(model, question, context, isn, think):
    tmpl = NUMERICAL_PROMPT_TEMPLATE if isn else THEORY_PROMPT_TEMPLATE
    payload = {"model": model,
               "prompt": tmpl.format(context=context, question=question),
               "stream": False, "think": think,
               "options": {"num_ctx": NUM_CTX, "temperature": 0.1,
                           "num_predict": 2048 if isn else 512},
               "keep_alive": "5m"}
    t0 = time.perf_counter()
    r = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=300)
    wall = time.perf_counter() - t0
    r.raise_for_status()
    b = r.json()
    return {"answer_full": b.get("response", "").strip(),
            "thinking_chars": len(b.get("thinking", "") or ""),
            "eval_count": b.get("eval_count", 0),
            "tok_s": round(b.get("eval_count", 0) / max(b.get("eval_duration", 1) / 1e9, 1e-9), 1),
            "wall_s": round(wall, 1)}

out = {"results": []}
# (a) full-capture default-think re-runs for manual verification
for cid in (21, 24, 42):
    q = by_id[cid]
    isn = is_numerical_question(q["question"])
    chunks = R.retrieve(q["question"], limit=6)
    formulas = R.retrieve_formulas(q["question"], limit=3) if isn else None
    ctx = build_context_string(chunks, formulas)
    g = gen("qwen3:8b", q["question"], ctx, isn, None)
    ok = grade_answer_llm(q["question"], g["answer_full"], q["ground_truth_answer"])
    out["results"].append({"id": cid, "arm": "qwen3-default-fullcap", **g,
                           "grader_correct": ok})
    print(f"id={cid} default: correct={ok} wall={g['wall_s']}s", flush=True)

# (b) think:false arm, 8 questions, 1 trial each
for cid in (1, 21, 22, 23, 24, 41, 42, 65):
    q = by_id[cid]
    isn = is_numerical_question(q["question"])
    chunks = R.retrieve(q["question"], limit=6)
    formulas = R.retrieve_formulas(q["question"], limit=3) if isn else None
    ctx = build_context_string(chunks, formulas)
    g = gen("qwen3:8b", q["question"], ctx, isn, False)
    ok = grade_answer_llm(q["question"], g["answer_full"], q["ground_truth_answer"])
    g["answer_full"] = g["answer_full"][:1500]
    out["results"].append({"id": cid, "arm": "qwen3-nothink", **g,
                           "grader_correct": ok})
    print(f"id={cid} nothink: correct={ok} wall={g['wall_s']}s "
          f"tok={g['eval_count']} think={g['thinking_chars']}", flush=True)

with open("think_probe_results.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("WROTE think_probe_results.json", flush=True)
shutil.rmtree(TMP_DB, ignore_errors=True)
