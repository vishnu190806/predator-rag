"""Offline prompt experiment: current templates (A) vs tightened templates (B).

Same isolated physics corpus (./chroma_promptlab, cache-hit), same retrieval
(limit=6 + formulas for numerical), same grader as benchmark.py.
Questions: the 9 benchmark cases graded INCORRECT + 2 graded-CORRECT controls.
Writes: prompt_lab_results.json. Production code untouched.
"""
import json, os, shutil, sys, time
sys.stdout.reconfigure(encoding="utf-8")

TMP_DB = "./chroma_promptlab"
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

from answer import (build_context_string, is_numerical_question, OLLAMA_MODEL,
                    OLLAMA_HOST, NUM_CTX, THEORY_PROMPT_TEMPLATE,
                    NUMERICAL_PROMPT_TEMPLATE)
from benchmark import grade_answer_llm
import requests

EXTRA_THEORY = """
* Prefer the source whose section heading most directly matches the question
  topic; do not build the answer from an unrelated section (e.g. do not use
  spring-force sections to answer a general work-definition question).
* Quote the exact textbook statement or formula you rely on before paraphrasing.
"""
EXTRA_NUM = """
* NEVER assume a value that is not stated (e.g. do not assume two masses are
  equal, do not invent g=10 unless computing a final decimal).
* Write every substitution on its own line and re-check signs and units:
  kinetic energy and squared quantities can never be negative.
* If the result contradicts a basic check (negative KE, missing friction when
  friction is given), redo the substitution step before finalizing.
"""

def gen(question, context, isn, extra):
    from answer import THEORY_PROMPT_TEMPLATE as T, NUMERICAL_PROMPT_TEMPLATE as N
    tmpl = (N if isn else T) + extra
    payload = {"model": OLLAMA_MODEL,
               "prompt": tmpl.format(context=context, question=question),
               "stream": False,
               "options": {"num_ctx": NUM_CTX, "temperature": 0.1,
                           "num_predict": 2048 if isn else 512},
               "keep_alive": "5m"}
    t0 = time.perf_counter()
    r = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=300)
    dt = time.perf_counter() - t0
    r.raise_for_status()
    return r.json().get("response", "").strip(), dt

bench = json.load(open("benchmark_questions.json", encoding="utf-8"))
by_id = {q["id"]: q for q in bench}
CASE_IDS = [1, 21, 22, 23, 24, 41, 42, 44, 45, 61, 65, 2, 25]  # 11 fail + 2 controls

out = {"conditions": {"A": "current templates", "B": "templates + grounding rules"},
       "results": []}
for cid in CASE_IDS:
    q = by_id[cid]
    question, gt = q["question"], q["ground_truth_answer"]
    isn = is_numerical_question(question)
    chunks = R.retrieve(question, limit=6)
    formulas = R.retrieve_formulas(question, limit=3) if isn else None
    ctx = build_context_string(chunks, formulas)
    row = {"id": cid, "is_num": isn, "question": question[:80]}
    for cond, extra in (("A", ""), ("B", EXTRA_THEORY if not isn else EXTRA_NUM)):
        ans, dt = gen(question, ctx, isn, extra)
        ok = grade_answer_llm(question, ans, gt)
        row[cond] = {"correct": ok, "seconds": round(dt, 1),
                     "answer_head": ans[:200]}
        print(f"id={cid} {cond}: correct={ok} t={dt:.1f}s", flush=True)
    out["results"].append(row)

with open("prompt_lab_results.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print("WROTE prompt_lab_results.json", flush=True)
shutil.rmtree(TMP_DB, ignore_errors=True)
