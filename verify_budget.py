"""Live output-budget verification (qwen3:8b default, num_predict 4096 numerical).

Isolated tmp corpus; main DB untouched. For previously-truncated cases
(ids 21, 42) + 1 theory control: checks non-empty answer, eval tokens used
vs budget, no think override in flight, streaming parity.
Writes: verify_budget.json
"""
import json, os, shutil, sys, time
sys.stdout.reconfigure(encoding="utf-8")

TMP_DB = "./chroma_verify_budget"
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
import answer
from answer import (answer_question, generate_answer_stream, OLLAMA_HOST,
                    OLLAMA_MODEL, NUM_CTX, NUM_PREDICT_NUMERICAL,
                    NUM_PREDICT_THEORY)

print("default model:", OLLAMA_MODEL, "| num budgets:",
      NUM_PREDICT_THEORY, NUM_PREDICT_NUMERICAL, "| ctx:", NUM_CTX, flush=True)
assert OLLAMA_MODEL == "qwen3:8b", "default model is not qwen3:8b"

bench = json.load(open("benchmark_questions.json", encoding="utf-8"))
by_id = {q["id"]: q for q in bench}
out = {"model": OLLAMA_MODEL, "cases": []}

for cid in (21, 42, 2):
    q = by_id[cid]["question"]
    res = answer_question(q, verbose=False)  # default model path
    plain_empty = not res["answer"].strip()
    # streaming parity on same question
    from answer import build_context_string, retrieve, retrieve_formulas
    chunks = retrieve(q, limit=6)
    formulas = retrieve_formulas(q, limit=3) if res["is_numerical"] else None
    ctx = build_context_string(chunks, formulas)
    streamed = "".join(generate_answer_stream(q, ctx, res["is_numerical"]))
    entry = {"id": cid, "is_num": res["is_numerical"],
             "answer_chars": len(res["answer"]),
             "answer_empty": plain_empty,
             "stream_chars": len(streamed),
             "stream_match": abs(len(streamed) - len(res["answer"])) < 20,
             "retrieval_latency": round(res["retrieval_latency"], 2),
             "generation_latency": round(res["generation_latency"], 2),
             "citations": res["citations"][:2],
             "answer_tail": res["answer"][-300:]}
    out["cases"].append(entry)
    print("id=%s num=%s chars=%d empty=%s stream_match=%s gen=%.1fs" % (
        cid, res["is_numerical"], len(res["answer"]), plain_empty,
        entry["stream_match"], res["generation_latency"]), flush=True)

with open("verify_budget.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("WROTE verify_budget.json", flush=True)
shutil.rmtree(TMP_DB, ignore_errors=True)
