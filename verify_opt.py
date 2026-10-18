"""Post-optimization verification on an isolated physics corpus.

Uses ./chroma_verify_tmp (deleted at the end); the real ./chroma_db is
untouched. Measures: parse/chunk, cold embed (CPU), cache-hit re-ingest,
retrieval quality on physics questions, streaming parity, e2e generation.
Writes: verify_opt.json
"""
import json, os, shutil, sys, time
sys.stdout.reconfigure(encoding="utf-8")

TMP_DB = "./chroma_verify_tmp"
if os.path.exists(TMP_DB):
    shutil.rmtree(TMP_DB)

import ingest as I
import retrieve as R
I.CHROMA_DB_PATH = TMP_DB
R.CHROMA_DB_PATH = TMP_DB

PHYS = ["data/keph105.pdf", "data/keph106.pdf", "data/keph107.pdf"]
out = {"stages": {}, "quality": [], "e2e": {}}

# 1. Parse + chunk physics subset
t0 = time.perf_counter()
staged = []
for pdf in PHYS:
    pb, chunks = I._parse_and_chunk_pdf(pdf, os.path.basename(pdf))
    staged.append((pb, os.path.basename(pdf), chunks))
dt_parse = time.perf_counter() - t0
n_chunks = sum(len(c) for _, _, c in staged)
type_counts = {}
for _, _, c in staged:
    for x in c:
        type_counts[x["type"]] = type_counts.get(x["type"], 0) + 1
out["stages"]["parse_3phys_s"] = round(dt_parse, 2)
out["stages"]["phys_chunks"] = n_chunks
out["stages"]["phys_types"] = type_counts
print(f"parse 3 physics PDFs: {dt_parse:.2f}s -> {n_chunks} chunks {type_counts}", flush=True)

# 2. Cold embed (CPU singleton) + store
t0 = time.perf_counter()
import chromadb
client = chromadb.PersistentClient(path=TMP_DB)
coll = client.get_or_create_collection(R.COLLECTION_NAME)
all_t, all_e, all_m = [], [], []
for pb, disp, chunks in staged:
    t, e, m = I._embed_chunks_cached(pb, disp, chunks)
    all_t.extend(t); all_e.extend(e); all_m.extend(m)
dt_embed = time.perf_counter() - t0
out["stages"]["cold_embed_3phys_s"] = round(dt_embed, 2)
out["stages"]["per_chunk_ms"] = round(dt_embed / max(n_chunks, 1) * 1000, 1)
print(f"cold embed {n_chunks}: {dt_embed:.2f}s ({dt_embed/max(n_chunks,1)*1000:.1f} ms/chunk)", flush=True)
t0 = time.perf_counter()
I._add_to_collection(coll, all_t, all_e, all_m)
out["stages"]["chroma_add_s"] = round(time.perf_counter() - t0, 2)
print(f"chroma add: {out['stages']['chroma_add_s']}s count={coll.count()}", flush=True)

# 3. Cache-hit re-ingest (simulates clean-start re-upload of unchanged PDFs)
t0 = time.perf_counter()
for pb, disp, chunks in staged:
    I._embed_chunks_cached(pb, disp, chunks)
out["stages"]["cache_hit_reembed_s"] = round(time.perf_counter() - t0, 2)
print(f"cache-hit re-embed: {out['stages']['cache_hit_reembed_s']}s", flush=True)

# 4. Retrieval quality on physics questions (expect physics sections, not maths)
R.initialize_retrieval_components()
QUALITY_CASES = [
    ("State Kepler's third law of periods.", ["7.2", "kepler"]),
    ("State the Universal Law of Gravitation.", ["7.3", "gravitation"]),
    ("Define power and write its SI unit.", ["5.10", "power"]),
    ("What is the relation between torque and angular momentum?", ["6.7", "torque", "angular momentum"]),
    ("A solid cylinder of mass 20 kg rotates at 100 rad/s, radius 0.25 m. Kinetic energy of rotation?", ["6.9", "moment of inertia", "kinetic"]),
    ("Write the formula for escape velocity.", ["7.6", "escape", "7.8"]),
]
for q, expects in QUALITY_CASES:
    t0 = time.perf_counter()
    hits = R.retrieve(q, limit=6)
    dt = time.perf_counter() - t0
    top3 = " | ".join(h["metadata"].get("section", "?") for h in hits[:3]).lower()
    hit_ok = any(e.lower() in top3 for e in expects)
    out["quality"].append({"q": q, "ok": hit_ok, "latency_s": round(dt, 3),
                           "top3": [h["metadata"].get("section", "?") for h in hits[:3]]})
    print(f"[{'HIT' if hit_ok else 'MISS'}] {dt:.3f}s {q[:50]} -> {out['quality'][-1]['top3'][0][:60]}", flush=True)

# 5. Streaming parity + e2e generation with NUM_CTX
import requests
from answer import (build_context_string, generate_answer, generate_answer_stream,
                    NUM_CTX, OLLAMA_HOST, OLLAMA_MODEL, is_numerical_question)
for kind, q, isn, cap in [
    ("theory", "State Kepler's third law of periods.", False, 512),
    ("numerical", "A solid cylinder of mass 20 kg rotates at 100 rad/s, radius 0.25 m. What is the kinetic energy of rotation?", True, 2048),
]:
    chunks = R.retrieve(q, limit=6)
    formulas = R.retrieve_formulas(q, limit=3) if isn else None
    ctx = build_context_string(chunks, formulas)
    t0 = time.perf_counter()
    streamed = "".join(generate_answer_stream(q, ctx, isn))
    dt_stream = time.perf_counter() - t0
    ans, dt_plain = generate_answer(q, ctx, isn)
    out["e2e"][kind] = {
        "ctx": NUM_CTX, "is_num": is_numerical_question(q),
        "stream_s": round(dt_stream, 2), "plain_s": round(dt_plain, 2),
        "stream_chars": len(streamed), "plain_chars": len(ans),
        "len_match": abs(len(streamed) - len(ans)) < 20,
        "answer_head": ans[:250],
    }
    print(f"{kind}: stream={dt_stream:.2f}s plain={dt_plain:.2f}s chars={len(ans)} match={out['e2e'][kind]['len_match']}", flush=True)
    print(f"  head: {ans[:150]}", flush=True)

with open("verify_opt.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print("WROTE verify_opt.json", flush=True)
shutil.rmtree(TMP_DB, ignore_errors=True)
print("cleaned tmp db", flush=True)
