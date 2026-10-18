"""Controlled LLM A/B: llama3.1:8b vs qwen3:8b on the 11 benchmark failures.

Fairness controls: identical frozen contexts (retrieved once, reused for both
models and all trials), identical prompt templates, identical num_ctx=4096 /
temperature=0.1 / num_predict caps, identical payload shape (no think param —
drop-in replacement test), same grader (llama3.1:8b, temp 0) for both arms.
2 generation trials per question per model (13 Qs: 11 fails + 2 controls).
Writes: model_lab_results.json. Production code and main DB untouched.
"""
import json, os, shutil, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8")

TMP_DB = "./chroma_modellab"
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
print(f"lab corpus: {coll.count()} chunks", flush=True)
R.initialize_retrieval_components()

import requests
from answer import (build_context_string, is_numerical_question, OLLAMA_HOST,
                    NUM_CTX, THEORY_PROMPT_TEMPLATE, NUMERICAL_PROMPT_TEMPLATE)
from benchmark import grade_answer_llm

MODELS = ["llama3.1:8b", "qwen3:8b"]
GRADER = "llama3.1:8b"
TRIALS = 2

bench = json.load(open("benchmark_questions.json", encoding="utf-8"))
by_id = {q["id"]: q for q in bench}
QIDS = [1, 21, 22, 23, 24, 41, 42, 44, 45, 61, 65, 2, 25]

def vram_mb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"], stderr=subprocess.DEVNULL)
        return float(out.decode().strip().split("\n")[0])
    except Exception:
        return -1.0

def warm(model):
    t0 = time.perf_counter()
    requests.post(f"{OLLAMA_HOST}/api/generate",
                  json={"model": model, "prompt": "", "stream": False,
                        "options": {"num_ctx": NUM_CTX}}, timeout=300)
    return round(time.perf_counter() - t0, 1)

def gen(model, question, context, isn):
    tmpl = NUMERICAL_PROMPT_TEMPLATE if isn else THEORY_PROMPT_TEMPLATE
    payload = {"model": model,
               "prompt": tmpl.format(context=context, question=question),
               "stream": False,
               "options": {"num_ctx": NUM_CTX, "temperature": 0.1,
                           "num_predict": 2048 if isn else 512},
               "keep_alive": "5m"}
    t0 = time.perf_counter()
    r = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=300)
    wall = time.perf_counter() - t0
    r.raise_for_status()
    b = r.json()
    return {"answer": b.get("response", "").strip(),
            "thinking_chars": len(b.get("thinking", "") or ""),
            "eval_count": b.get("eval_count", 0),
            "eval_dur_s": round(b.get("eval_duration", 0) / 1e9, 2),
            "prompt_tok": b.get("prompt_eval_count", 0),
            "tok_s": round(b.get("eval_count", 0) / max(b.get("eval_duration", 1) / 1e9, 1e-9), 1),
            "wall_s": round(wall, 1)}

def citations_valid(answer_cites, chunks):
    premium = " ".join(answer_cites).lower()
    secs = [c["metadata"].get("section", "").lower() for c in chunks]
    return any(s[:20] in premium for s in secs if s)

# Freeze contexts once (identical input for both models, all trials)
frozen = {}
for cid in QIDS:
    q = by_id[cid]
    isn = is_numerical_question(q["question"])
    chunks = R.retrieve(q["question"], limit=6)
    formulas = R.retrieve_formulas(q["question"], limit=3) if isn else None
    frozen[cid] = {"question": q["question"], "gt": q["ground_truth_answer"],
                   "is_num": isn,
                   "context": build_context_string(chunks, formulas),
                   "chunk_secs": [c["metadata"].get("section", "?") for c in chunks]}

out = {"models": MODELS, "grader": GRADER, "trials": TRIALS, "num_ctx": NUM_CTX,
       "results": [], "resources": {}}
for model in MODELS:
    out["resources"][model] = {"vram_before_mb": vram_mb()}
    out["resources"][model]["warm_s"] = warm(model)
    out["resources"][model]["vram_after_warm_mb"] = vram_mb()
    print(f"warmed {model}: {out['resources'][model]['warm_s']}s, "
          f"vram={out['resources'][model]['vram_after_warm_mb']}MB", flush=True)

for cid in QIDS:
    f = frozen[cid]
    row = {"id": cid, "is_num": f["is_num"], "question": f["question"][:80],
           "arms": {}}
    for model in MODELS:
        trials = []
        for t in range(TRIALS):
            g = gen(model, f["question"], f["context"], f["is_num"])
            ok = grade_answer_llm(f["question"], g["answer"], f["gt"])
            trials.append({**g, "answer": g["answer"][:400],
                           "grader_correct": ok})
            print(f"id={cid} {model} t{t}: correct={ok} "
                  f"wall={g['wall_s']}s tok={g['eval_count']} "
                  f"think_chars={g['thinking_chars']}", flush=True)
        row["arms"][model] = trials
    out["results"].append(row)

with open("model_lab_results.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("WROTE model_lab_results.json", flush=True)
shutil.rmtree(TMP_DB, ignore_errors=True)
