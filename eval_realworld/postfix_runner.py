"""Resumable post-fix real-world evaluation runner (Oct 2026).

Why this exists
---------------
The first post-fix attempt (`eval_realworld.py --with-llm`) stalled: qwen3:8b
thinking occasionally consumes the whole 2048/4096-token budget, and
`generate_answer` maps that to the honest EMPTY_ANSWER_MESSAGE after a
`requests` timeout of 300 s. The harness then retried once, so ONE unlucky
question could block ~600 s and a single process-wide stall risked losing the
whole run. That run stopped at 7/60.

Design (satisfies the post-fix validation requirements)
-------------------------------------------------------
* Parent/worker split. The parent holds NO model and NO database; it only
  sends one question id at a time and enforces a bounded wall-clock budget.
  The worker owns retrieval + generation and streams one JSON result per
  question to a JSONL file.
* Independence: if a question exceeds its budget, the parent kills the worker,
  records the question as `timeout`, and restarts a fresh worker. A stall can
  never prevent remaining questions from completing.
* Bounded transport: every Ollama call is wrapped so a request-level failure
  is caught and recorded, never raised out of the run.
* Resume: results are appended to the JSONL after every question and the
  driver skips any id already recorded. Re-running the command continues.
* At most one retry per question. First-attempt and retry outcomes are both
  persisted under `attempts[]`, so nothing is overwritten or lost.
* Thinking text is never captured: the worker uses the production
  `answer_question`, which returns only the final `response` field, and the
  recorder strips any residual <think> block before writing.
* A missing/timed-out/empty answer is recorded with its status and graded as
  INCORRECT unless the question is an `absent`/abstain question that is
  correctly declined. It is never silently dropped from the denominator.

Production code is NOT modified: prompts, retrieval settings, model, context
size and token budgets are the shipped values.

Usage
-----
    python eval_realworld/postfix_runner.py
    python eval_realworld/postfix_runner.py --rebuild     # fresh index+cache
    python eval_realworld/postfix_runner.py --report      # summarize only
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

CORPUS = os.path.join(HERE, "real_corpus")
WORK = os.path.join(HERE, "tmp_postfix")
CHROMA = os.path.join(WORK, "chroma")
CACHE = os.path.join(WORK, "cache")
STREAM = os.path.join(WORK, "results_stream.jsonl")
LOG = os.path.join(WORK, "worker.log")
STATE = os.path.join(HERE, "postfix_results.json")

FILES = ["faa_weather.pdf", "faa_drones.pdf", "frankenstein.docx",
         "whale_slides.pptx", "worldbank.xlsx", "usgs_jan2024.csv",
         "awesome_nodejs.md", "wcag22.html", "express_package.json",
         "bluewhale_export.xml"]

# Post-fix chunk counts measured from the shipped extractors. Used by the
# worker as a self-check that a stale 12-row cache can never contaminate a run.
EXPECTED_CHUNKS = {
    "faa_weather.pdf": 1223, "faa_drones.pdf": 553,
    "frankenstein.docx": 142, "whale_slides.pptx": 7,
    "worldbank.xlsx": 9,      # was 7 with 12-row XLSX groups
    "usgs_jan2024.csv": 132,  # was 48 with 12-row CSV groups
    "awesome_nodejs.md": 154, "wcag22.html": 360,
    "express_package.json": 5,  # 4000->600 char record blocks (ext-v4)
    "bluewhale_export.xml": 115,
}

# Wall clock for ONE generation attempt. The prior full run's slowest
# generation was 52.9 s; 200 s is a ~4x margin that still bounds a genuine
# stall (a thinking run that overruns the 300 s requests timeout inside
# answer.generate_answer). Must stay BELOW that 300 s so the parent's kill is
# the backstop for a dead socket, not a duplicate of the library timeout.
PER_QUESTION_BUDGET_S = 200
WORKER_BOOT_TIMEOUT_S = 300   # model load + index build for a fresh worker
MAX_ATTEMPTS = 2              # one initial attempt + at most one retry


# --------------------------------------------------------------- worker ---
def worker_main():
    """Owns retrieval + generation. Streams JSONL results to STREAM."""
    import re
    import traceback

    sys.path.insert(0, ROOT)
    import ingest
    import retrieve
    import extractors
    from answer import (answer_question, format_citations, location_label,
                        is_empty_answer, is_numerical_question,
                        generate_answer_stream, build_context_string)

    ingest.CHROMA_DB_PATH = CHROMA
    ingest.EMBED_CACHE_DIR = CACHE
    retrieve.CHROMA_DB_PATH = CHROMA
    retrieve._db_client = None
    retrieve._collection = None
    retrieve._bm25 = None
    retrieve._corpus_data = None

    # Reuse the exact question definitions from the original harness so the
    # runs stay comparable. BOTH graders are recorded on every result so any
    # future score can be recomputed offline in either convention:
    #   check_answer_legacy    - the original substring scorer (eval_realworld)
    #   check_answer_corrected - numeric-aware scorer (eval_realworld/grader.py)
    sys.path.insert(0, HERE)
    from eval_realworld import HELDOUT, CALIB
    from grader import (check_answer_corrected, check_answer_legacy,
                        source_coverage)

    meta = {
        "extractor_version": extractors.EXTRACTOR_VERSION,
        "cache_version": ingest.CACHE_VERSION,
        "chunks": {},
    }

    def log(msg):
        print(msg, file=sys.stderr, flush=True)

    def record(obj):
        with open(STREAM, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            f.flush()

    # ---- build / verify the isolated index ---------------------------------
    t0 = time.perf_counter()
    need_build = not os.path.exists(os.path.join(CHROMA, "chroma.sqlite3"))
    if need_build:
        os.makedirs(CHROMA, exist_ok=True)
        os.makedirs(CACHE, exist_ok=True)
        for i, fname in enumerate(FILES):
            n = ingest.ingest_file(os.path.join(CORPUS, fname),
                                   recreate=(i == 0), original_filename=fname)
            meta["chunks"][fname] = n
            log(f"indexed {fname}: {n} chunks")
    else:
        docs = ingest.list_documents()
        meta["chunks"] = docs
        log(f"reusing existing index: {docs}")
    meta["index_build_s"] = round(time.perf_counter() - t0, 2)
    bad = {f: (meta["chunks"].get(f), e)
           for f, e in EXPECTED_CHUNKS.items()
           if meta["chunks"].get(f) != e}
    if bad:
        log(f"FATAL chunk-count mismatch (stale cache?): {bad}")
        record({"type": "fatal", "reason": "chunk_mismatch", "detail": bad})
        return
    log(f"chunk counts verified: {meta['chunks']}")
    record({"type": "meta", **meta})

    retrieve.initialize_retrieval_components()

    by_id = {q["id"]: q for q in HELDOUT}
    by_id.update({q["id"]: q for q in CALIB})

    def score(item):
        """Deterministic retrieval / location / citation scoring."""
        t = time.perf_counter()
        hits = retrieve.retrieve(item["q"], limit=3)
        hits6 = retrieve.retrieve(item["q"], limit=6)
        rtr = time.perf_counter() - t
        files3 = [h["metadata"]["file"] for h in hits]
        files6 = [h["metadata"]["file"] for h in hits6]
        accepted = item.get("file") or item.get("files_all")
        if accepted:
            need = item.get("files_all", [item.get("file")])
            r3 = 1.0 if ((item.get("files_all") and
                          all(f in files6 for f in need)) or
                         (not item.get("files_all") and
                          item["file"] in files3)) else 0.0
            r6 = 1.0 if all(f in files6 for f in need) else 0.0
        else:
            r3 = 1.0
            r6 = 1.0
        # Corrected source coverage. A cross-document question is only FULLY
        # retrieved when EVERY required source is present at the depth being
        # measured. The legacy branch below silently evaluated `files_all`
        # questions against files6, so a partial retrieval would be mislabelled
        # as full at depth 3. `source_coverage` separates the two depths and
        # also distinguishes "at least one required source" from "all".
        cov = source_coverage(item, files3, files6)
        if cov["has_expected_source"]:
            r3 = 1.0 if cov["all_required_at3"] else 0.0
            r6 = 1.0 if cov["all_required_at6"] else 0.0
        else:
            # No expected source (abstain questions): retrieval is not scored.
            r3 = r6 = None
        if item.get("loc") and r3:
            loc = 1.0 if any(item["loc"].lower() in
                             location_label(h["metadata"]).lower()
                             for h in hits
                             if h["metadata"]["file"] ==
                             (item.get("file") or files3[0])) else 0.0
        else:
            loc = 1.0
        cits = format_citations(hits)
        return {
            "recall3": r3, "recall6": r6, "loc": loc,
            "cit": 1.0 if cits else 0.0,
            "files3": files3, "files6": files6,
            "coverage": cov,
            "rtr_s": round(rtr, 3), "citations": cits,
        }

    def run_one(item):
        """Deterministic scoring + one bounded generation attempt."""
        s = score(item)
        t1 = time.perf_counter()
        status = "ok"
        err = ""
        try:
            ans = answer_question(item["q"], verbose=False)
            text = ans.get("answer", "") or ""
            citations = ans.get("citations", []) or []
        except Exception as exc:                      # bounded transport safety
            text, citations = "", []
            status, err = "error", f"{type(exc).__name__}: {exc}"
            log(f"{item['id']} generation error {err}")
        wall = time.perf_counter() - t1

        if status == "ok":
            if is_empty_answer(text):
                status = "empty"
            elif not text.strip():
                status = "empty"

        # Thinking text must never be persisted. Production already returns
        # only the final response, but strip defensively so a leak would be
        # caught rather than stored.
        if "<think" in text.lower() or "</think>" in text.lower():
            status = "thinking_leak"
        text = re.sub(r"<think>.*?</think>", "", text,
                      flags=re.DOTALL | re.IGNORECASE).strip()

        # Both graders are recorded so any score can be recomputed offline in
        # either convention; `ans` is the corrected one from now on.
        ok_new, kw_new = check_answer_corrected(item, text)
        ok_old, kw_old = check_answer_legacy(item, text)

        rec = dict(s)
        rec.update({
            "id": item["id"], "cat": item.get("cat", "calib"), "q": item["q"],
            "status": status, "error": err,
            "wall_s": round(wall, 2),
            "gen_s": ans.get("generation_latency", -1.0) if status == "ok" else -1.0,
            "ans": 1.0 if ok_new else 0.0, "kw": kw_new,
            "ans_legacy": 1.0 if ok_old else 0.0, "kw_legacy": kw_old,
            "answer": text[:1200], "citations": citations,
            "abstain_expect": bool(item.get("abstain")),
        })
        return rec

    # ---- serve requests ----------------------------------------------------
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            spec = json.loads(line)
        except ValueError:
            continue
        if spec.get("cmd") == "shutdown":
            break
        qid = spec.get("id")
        item = by_id.get(qid)
        if item is None:
            record({"type": "unknown", "id": qid})
            continue
        try:
            rec = run_one(item)
        except Exception:
            rec = {"id": qid, "cat": item.get("cat"), "q": item["q"],
                   "status": "error",
                   "error": traceback.format_exc(limit=2)[:400],
                   "recall3": 0.0, "recall6": 0.0, "loc": 0.0, "cit": 0.0,
                   "ans": 0.0, "kw": [], "citations": [], "wall_s": -1.0,
                   "gen_s": -1.0, "answer": "", "files3": [], "files6": [],
                   "rtr_s": -1.0}
        rec["type"] = "result"
        rec["attempt"] = spec.get("attempt", 1)
        record(rec)
        log(f"done {qid} status={rec['status']} ans={rec['ans']} "
            f"wall={rec['wall_s']}s")


# ---------------------------------------------------------------- parent ---
def read_stream():
    rows = []
    if not os.path.exists(STREAM):
        return rows
    with open(STREAM, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def build_state():
    rows = read_stream()
    meta = next((r for r in rows if r.get("type") == "meta"), {})
    results = {}
    for r in rows:
        if r.get("type") != "result":
            continue
        qid = r.get("id")
        results.setdefault(qid, {"attempts": []})["attempts"].append(
            {k: v for k, v in r.items() if k != "type"})
    return meta, results


def start_worker():
    env = dict(os.environ)
    return subprocess.Popen(
        [sys.executable, "-u", os.path.abspath(__file__), "--worker"],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=open(LOG, "a", encoding="utf-8"),
        cwd=ROOT, env=env, text=True, bufsize=1)


def seen_pairs():
    """(qid, attempt) pairs already persisted in the JSONL."""
    out = set()
    for r in read_stream():
        if r.get("type") == "result":
            out.add((r.get("id"), r.get("attempt")))
    return out


def wait_for(proc, qid, attempt, budget):
    """Poll the JSONL until this question's attempt lands or budget expires."""
    deadline = time.time() + budget
    while time.time() < deadline:
        if proc.poll() is not None:
            return "worker_died"
        if (qid, attempt) in seen_pairs():
            return "ok"
        time.sleep(0.5)
    return "timeout"


def drive(question_ids):
    os.makedirs(WORK, exist_ok=True)
    if "--rebuild" in sys.argv:
        shutil.rmtree(CHROMA, ignore_errors=True)
        shutil.rmtree(CACHE, ignore_errors=True)
        if os.path.exists(STREAM):
            os.remove(STREAM)

    _, results = build_state()
    todo = [q for q in question_ids
            if not any(a.get("status") == "ok" or a.get("status") == "empty"
                       for a in results.get(q, {}).get("attempts", []))]
    print(f"questions: {len(question_ids)} | already satisfied: "
          f"{len(question_ids) - len(todo)} | to run: {len(todo)}")

    proc = None
    try:
        for qid in todo:
            done = False
            for attempt in range(1, MAX_ATTEMPTS + 1):
                if proc is None or proc.poll() is not None:
                    proc = start_worker()
                    time.sleep(1.0)
                    boot_deadline = time.time() + WORKER_BOOT_TIMEOUT_S
                    booted = False
                    while time.time() < boot_deadline:
                        if any(r.get("type") == "meta"
                               for r in read_stream()):
                            booted = True
                            break
                        if proc.poll() is not None:
                            break
                        time.sleep(1.0)
                    if not booted:
                        print(f"[{qid}] worker failed to boot")
                        continue

                try:
                    proc.stdin.write(json.dumps({"id": qid,
                                                 "attempt": attempt}) + "\n")
                    proc.stdin.flush()
                except (BrokenPipeError, ValueError):
                    proc = None
                    continue

                state = wait_for(proc, qid, attempt,
                                 PER_QUESTION_BUDGET_S)
                if state == "ok":
                    done = True
                    break
                # timeout / worker death: record explicit failure, keep going
                _, results = build_state()
                results.setdefault(qid, {"attempts": []})
                prev = (results[qid]["attempts"][0]
                        if results[qid]["attempts"] else {})
                results[qid]["attempts"].append({
                    "id": qid, "attempt": attempt, "type": "result",
                    "status": ("timeout" if state == "timeout"
                               else "worker_died"),
                    "ans": 0.0, "kw": [], "citations": [], "answer": "",
                    "error": f"parent observed {state} after "
                             f"{PER_QUESTION_BUDGET_S}s",
                    "recall3": prev.get("recall3", 0.0),
                    "recall6": prev.get("recall6", 0.0),
                    "loc": prev.get("loc", 0.0), "cit": prev.get("cit", 0.0),
                    "files3": prev.get("files3", []),
                    "files6": prev.get("files6", []),
                    "rtr_s": prev.get("rtr_s", -1.0),
                    "wall_s": PER_QUESTION_BUDGET_S, "gen_s": -1.0,
                    "q": prev.get("q", qid),
                    "cat": prev.get("cat", ""),
                })
                save(results)
                print(f"[{qid}] attempt {attempt}: {state}")
                try:
                    proc.kill()
                except Exception:
                    pass
                proc = None
                time.sleep(2.0)
            if not done:
                print(f"[{qid}] unresolved after {MAX_ATTEMPTS} attempts")
    finally:
        if proc is not None:
            try:
                proc.stdin.write(json.dumps({"cmd": "shutdown"}) + "\n")
                proc.stdin.flush()
                proc.wait(timeout=10)
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
    return build_state()


def r_ok(a):
    return a.get("status") in ("ok", "empty")


def save(results):
    meta = next((r for r in read_stream() if r.get("type") == "meta"), {})
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results}, f, indent=2,
                  ensure_ascii=False)


# ---------------------------------------------------------------- report ---
def report():
    from collections import defaultdict
    sys.path.insert(0, HERE)
    from eval_realworld import HELDOUT
    ids = {q["id"]: q for q in HELDOUT}
    meta, results = build_state()

    rows = []
    for qid, rec in results.items():
        ats = rec["attempts"]
        first = ats[0] if ats else {}
        # final outcome = first ok/empty attempt, else last recorded attempt
        final = next((a for a in ats if r_ok(a)), ats[-1] if ats else {})
        rows.append({"id": qid, "cat": ids.get(qid, {}).get("cat", "?"),
                     "first": first, "final": final, "n_attempts": len(ats)})

    out = {"meta": meta, "n_questions": len(HELDOUT),
           "n_recorded": len(rows)}
    completed = [r for r in rows if r["final"].get("status") in ("ok", "empty")]
    timedout = [r for r in rows if r["final"].get("status") == "timeout"]
    errored = [r for r in rows if r["final"].get("status") == "error"]
    retried = [r for r in rows if r["n_attempts"] > 1]
    out["stats"] = {
        "completed": len(completed), "timed_out": len(timedout),
        "errors": len(errored), "retried": len(retried),
        "missing": len(HELDOUT) - len(rows),
        "empty_responses": sum(1 for r in rows
                               if r["final"].get("status") == "empty"),
    }
    if rows:
        out["metrics"] = {
            "answer_accuracy": round(sum(r["final"].get("ans", 0)
                                         for r in rows) / len(rows), 4),
            "recall3": round(sum(r["final"].get("recall3", 0)
                                 for r in rows) / len(rows), 4),
            "recall6": round(sum(r["final"].get("recall6", 0)
                                 for r in rows) / len(rows), 4),
            "loc": round(sum(r["final"].get("loc", 0)
                             for r in rows) / len(rows), 4),
            "cit": round(sum(r["final"].get("cit", 0)
                             for r in rows) / len(rows), 4),
        }
        walls = sorted(r["final"].get("wall_s", -1) for r in completed
                       if r["final"].get("wall_s", -1) >= 0)
        if walls:
            out["latency"] = {
                "n": len(walls),
                "median_wall_s": walls[len(walls) // 2],
                "p95_wall_s": walls[min(len(walls) - 1,
                                        int(len(walls) * 0.95))],
            }
        cats = defaultdict(list)
        for r in rows:
            cats[r["cat"]].append(r)
        out["by_cat"] = {}
        for c, rs in sorted(cats.items()):
            out["by_cat"][c] = {
                "n": len(rs),
                "ans": round(sum(x["final"].get("ans", 0)
                                 for x in rs) / len(rs), 4),
                "recall3": round(sum(x["final"].get("recall3", 0)
                                     for x in rs) / len(rs), 4),
                "recall6": round(sum(x["final"].get("recall6", 0)
                                     for x in rs) / len(rs), 4),
                "loc": round(sum(x["final"].get("loc", 0)
                                 for x in rs) / len(rs), 4),
                "timeouts": sum(1 for x in rs
                                if x["final"].get("status") in
                                ("timeout", "worker_died")),
            }
    table_ids = ["wb1", "wb2", "wb3", "wb4", "wb5", "wb6", "wb7", "wb8",
                 "eq1", "eq2", "eq3", "eq4", "eq5"]
    out["table_questions"] = {
        r["id"]: {"status": r["final"].get("status"),
                  "ans": r["final"].get("ans"),
                  "kw": r["final"].get("kw"),
                  "answer": r["final"].get("answer", "")[:220]}
        for r in rows if r["id"] in table_ids}
    out["failures"] = [
        {"id": r["id"], "cat": r["cat"], "status": r["final"].get("status"),
         "recall3": r["final"].get("recall3"),
         "answer": r["final"].get("answer", "")[:300]}
        for r in rows if not r["final"].get("ans")]
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return out


def main():
    if "--worker" in sys.argv:
        worker_main()
        return
    if "--report" in sys.argv:
        report()
        return
    sys.path.insert(0, HERE)
    from eval_realworld import HELDOUT
    ids = [q["id"] for q in HELDOUT]
    t0 = time.time()
    _, results = drive(ids)
    save(results)
    print(f"\ndrive finished in {time.time() - t0:.1f}s")
    report()


if __name__ == "__main__":
    main()
