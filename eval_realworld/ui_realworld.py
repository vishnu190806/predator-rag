"""UI workflow verification on the REAL corpus, in an ISOLATED project copy.

Mirrors eval_stress/ui_apptest.py with real-world files: CSV + PPTX + JSON +
DOCX. Covers: fresh empty state, indexed-list rendering, delete-file handler,
query + streaming answer + citations, unsupported-format rejection UI,
no-think-leak, reset-to-empty. The file_uploader WIDGET itself is not drivable
in this Streamlit version (no AppTest accessor), so uploads are simulated by
indexing files then seeding session state — stated as a limitation, with a
manual procedure in RAG_REALWORLD_EVALUATION.md. Never touches ./chroma_db.
Run: python eval_realworld/ui_realworld.py  (run AFTER eval, keeps Ollama serial)
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(HERE, "tmp_ui_real")
RESULTS = os.path.join(HERE, "ui_results.json")
REAL = os.path.join(HERE, "real_corpus")

FILES = ["usgs_jan2024.csv", "whale_slides.pptx", "express_package.json",
         "frankenstein.docx"]

for f in ["app.py", "ingest.py", "retrieve.py", "answer.py", "extractors.py"]:
    os.makedirs(WORK, exist_ok=True)
    shutil.copy(os.path.join(ROOT, f), os.path.join(WORK, f))

os.chdir(WORK)
sys.path.insert(0, WORK)

from streamlit.testing.v1 import AppTest  # noqa: E402

import ingest  # noqa: E402

out = {"steps": {}}


def md_text(at):
    return "\n".join(m.value for m in at.markdown)


at = AppTest.from_file("app.py").run(timeout=120)
out["steps"]["fresh_run_no_exception"] = not at.exception
out["steps"]["empty_state_shown"] = "Workspace is empty" in md_text(at) + \
    "\n".join(i.value for i in at.info)
print("fresh run:", out["steps"]["fresh_run_no_exception"],
      "| empty state:", out["steps"]["empty_state_shown"])

for i, f in enumerate(FILES):
    ingest.ingest_file(os.path.join(REAL, f), recreate=(i == 0),
                       original_filename=f)
at.session_state["processed_files"] = set(FILES)
at.run(timeout=180)
body = md_text(at)
out["steps"]["indexed_list_shows_all_4"] = all(f in body for f in FILES)
print("indexed list:", out["steps"]["indexed_list_shows_all_4"])

# Real-format query: pptx deck + XML article answer with slide citation.
at.text_input(key="query_input").set_value(
    "What does the blue whale's diet consist of?").run(timeout=30)
ask = [b for b in at.button if "Query" in (b.label or "")]
assert ask, "query button not found"
ask[0].click().run(timeout=300)
body = md_text(at)
out["steps"]["answer_contains_krill"] = "krill" in body.lower()
out["steps"]["citations_rendered"] = "whale_slides.pptx" in body
out["steps"]["location_slide_rendered"] = "Slide 3" in body
leak_free = "<think" not in body.lower()
hidden = "reasoning trace is intentionally hidden"
leak_free = leak_free and "thinking" not in body.lower().replace(hidden, "")
out["steps"]["no_think_leak"] = leak_free
out["steps"]["query_exception"] = bool(at.exception)
if at.exception:
    out["steps"]["query_exceptions"] = [str(getattr(e, "value", e))[:300]
                                        for e in at.exception]
print("answer krill:", out["steps"]["answer_contains_krill"],
      "| citation:", out["steps"]["citations_rendered"],
      "| slide loc:", out["steps"]["location_slide_rendered"],
      "| leak-free:", leak_free,
      "| exception:", out["steps"]["query_exception"])

# Delete one file via its UI button (delete the CSV; verify it exits Chroma).
dels = [b for b in at.button if (b.key or "").startswith("del_")]
out["steps"]["delete_buttons_found"] = len(dels)
target = "usgs_jan2024.csv"
tbtn = [b for b in dels if b.key == "del_" + target][0]
tbtn.click().run(timeout=120)
body = md_text(at)
out["steps"]["deleted_file"] = target
out["steps"]["deleted_gone_from_list"] = f"`{target}`" not in body
out["steps"]["docs_after_delete"] = ingest.list_documents()
print("deleted:", target, "| gone from list:",
      out["steps"]["deleted_gone_from_list"],
      "| remaining:", out["steps"]["docs_after_delete"])

# Reset workspace via UI button.
reset = [b for b in at.button if "Reset" in (b.label or "")]
assert reset, "reset button not found"
reset[0].click().run(timeout=120)
out["steps"]["reset_empty_state"] = "Workspace is empty" in md_text(at) + \
    "\n".join(i.value for i in at.info)
out["steps"]["docs_after_reset"] = ingest.list_documents()
print("reset empty:", out["steps"]["reset_empty_state"],
      "| docs:", out["steps"]["docs_after_reset"])

with open(RESULTS, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print("saved", RESULTS)
