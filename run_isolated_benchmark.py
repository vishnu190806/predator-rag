"""Full 20-question benchmark against an ISOLATED physics corpus.

Why isolated: the main ./chroma_db currently holds only
Mathematics-Class-12-Part-2.pdf (7868 chunks), so physics benchmark
questions cannot be evaluated against it. This script builds
./chroma_bench_phys from keph105/106/107 (embed_cache HIT, seconds),
then runs benchmark.run_benchmark() unmodified against it.
The main DB is never touched. Output is renamed to
benchmark_isolated_phys628_qwen_results.json + a run manifest.
"""
import json, os, shutil, sys, time
sys.stdout.reconfigure(encoding="utf-8")

TMP_DB = "./chroma_bench_phys"
if os.path.exists(TMP_DB):
    shutil.rmtree(TMP_DB)

import ingest as I
import retrieve as R
I.CHROMA_DB_PATH = TMP_DB
R.CHROMA_DB_PATH = TMP_DB

# Build isolated physics corpus (cache-hit path, no re-encode)
import chromadb
PHYS = ["data/keph105.pdf", "data/keph106.pdf", "data/keph107.pdf"]
t0 = time.perf_counter()
client = chromadb.PersistentClient(path=TMP_DB)
coll = client.get_or_create_collection(R.COLLECTION_NAME)
at, ae, am = [], [], []
for pdf in PHYS:
    pb, chunks = I._parse_and_chunk_pdf(pdf, os.path.basename(pdf))
    t, e, m = I._embed_chunks_cached(pb, os.path.basename(pdf), chunks)
    at.extend(t); ae.extend(e); am.extend(m)
I._add_to_collection(coll, at, ae, am)
print(f"isolated corpus: {coll.count()} chunks in {time.perf_counter()-t0:.1f}s", flush=True)

# Run the unmodified benchmark harness against the isolated corpus
import benchmark as B
B.run_benchmark()

# Rename output + manifest so isolated results are never confused with full-corpus runs
os.replace("benchmark_results.json", "benchmark_isolated_phys628_qwen_results.json")
from answer import OLLAMA_MODEL, NUM_CTX, NUM_PREDICT_THEORY, NUM_PREDICT_NUMERICAL, GRADER_MODEL
manifest = {
    "corpus": "ISOLATED keph105/106/107 (physics ch 5-7), NOT the main DB",
    "corpus_chunks": coll.count(),
    "corpus_files": PHYS,
    "main_db_untouched": True,
    "generation_model": OLLAMA_MODEL,
    "grader_model": GRADER_MODEL,
    "num_ctx": NUM_CTX,
    "num_predict_theory": NUM_PREDICT_THEORY,
    "num_predict_numerical": NUM_PREDICT_NUMERICAL,
    "command": "python run_isolated_benchmark.py",
}
with open("benchmark_isolated_phys628_qwen_manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
print("WROTE benchmark_isolated_phys628_qwen_results.json + manifest", flush=True)
shutil.rmtree(TMP_DB, ignore_errors=True)
