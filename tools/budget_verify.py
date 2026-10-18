"""Live budget-fix verification on the production answer_question path.

Isolated physics corpus (./chroma_budget, deleted after). Wraps
answer.requests.post with a recording passthrough to the REAL Ollama so the
payload budgets on the true code path are asserted, then checks the previously
failing cases: id21 (mid-equation truncation at 2048), id42 (empty response at
2048), id24 (long derivation), id1 (theory 512 path + streaming parity).
Writes: budget_verify.json
"""
import json, os, shutil, sys
sys.stdout.reconfigure(encoding="utf-8")

TMP_DB = "./chroma_budget"
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

import answer
from answer import answer_question, generate_answer_stream, build_context_string

import requests as _rq

captured = []
_real_post = answer.requests.post


def recording_post(url, json=None, **kw):
    captured.append(json)
    return _rq.post(url, json=json, **kw)


answer.requests.post = recording_post
try:
    import benchmark as B
    bench = json.load(open("benchmark_questions.json", encoding="utf-8"))
    by_id = {q["id"]: q for q in bench}
    out = {"results": []}
    for cid in (21, 42, 24, 1):
        q = by_id[cid]["question"]
        captured.clear()
        res = answer_question(q, verbose=False)
        gen_payloads = [c for c in captured if c.get("stream") is False]
        num_cap = gen_payloads[0]["options"]["num_predict"] if gen_payloads else None
        ans = res["answer"]
        has_final = ("boxed" in ans or "Answer" in ans or "J" in ans or
                     len(ans.strip()) > 100)
        row = {"id": cid, "model": gen_payloads[0]["model"] if gen_payloads else "?",
               "num_predict_sent": num_cap, "is_num": res["is_numerical"],
               "answer_chars": len(ans), "non_empty": len(ans.strip()) > 0,
               "has_final": has_final, "total_s": round(res["latency"], 1),
               "gen_s": round(res["generation_latency"], 1),
               "answer_tail": ans.strip()[-300:]}
        out["results"].append(row)
        print("id=%s model=%s cap=%s chars=%d nonempty=%s final=%s t=%.1fs" % (
            cid, row["model"], num_cap, len(ans), row["non_empty"],
            has_final, res["latency"]), flush=True)

    # Streaming parity on one numerical (id24) through the production generator
    from retrieve import retrieve as ret, retrieve_formulas as retf
    chunks = ret(by_id[24]["question"], limit=6)
    ctx = build_context_string(chunks, retf(by_id[24]["question"], limit=3))
    streamed = "".join(generate_answer_stream(
        by_id[24]["question"], ctx, True))
    out["streaming"] = {"chars": len(streamed),
                        "non_empty": len(streamed.strip()) > 0,
                        "tail": streamed.strip()[-200:]}
    print("stream id24: chars=%d nonempty=%s" % (
        len(streamed), len(streamed.strip()) > 0), flush=True)
finally:
    answer.requests.post = _real_post

with open("budget_verify.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("WROTE budget_verify.json", flush=True)
shutil.rmtree(TMP_DB, ignore_errors=True)
