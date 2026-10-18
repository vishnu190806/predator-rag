"""UI workflow verification in an ISOLATED project copy (AppTest, no browser).

Covers: fresh empty state, indexed-list rendering, delete-file handler,
query + streaming answer + citations, reset-to-empty. The file_uploader
WIDGET itself is not drivable in this Streamlit version (no AppTest accessor),
so uploads are simulated by indexing files then seeding session state —
stated as a limitation. Never touches the real ./chroma_db.
Run: python eval_stress/ui_apptest.py
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(HERE, "tmp_ui")
RESULTS = os.path.join(HERE, "ui_results.json")

for f in ["app.py", "ingest.py", "retrieve.py", "answer.py", "extractors.py"]:
    os.makedirs(WORK, exist_ok=True)
    shutil.copy(os.path.join(ROOT, f), os.path.join(WORK, f))

os.chdir(WORK)
sys.path.insert(0, WORK)

from streamlit.testing.v1 import AppTest

import ingest

out = {"steps": {}}


def md_text(at):
    return "\n".join(m.value for m in at.markdown)


at = AppTest.from_file("app.py").run(timeout=120)
out["steps"]["fresh_run_no_exception"] = not at.exception
out["steps"]["fresh_exceptions"] = [str(getattr(e, "value", e))[:300] for e in (at.exception or [])]
body = md_text(at) + "\n".join(i.value for i in at.info)
out["steps"]["empty_state_shown"] = "Workspace is empty" in body
print("fresh run ok:", out["steps"]["fresh_run_no_exception"],
      "| empty state:", out["steps"]["empty_state_shown"])

# Simulate completed uploads of 3 formats.
corpus = os.path.join(HERE, "stress_corpus")
for i, f in enumerate(["memo.txt", "rates.xlsx", "safety_brief.pptx"]):
    ingest.ingest_file(os.path.join(corpus, f), recreate=(i == 0),
                       original_filename=f)
at.session_state["processed_files"] = {"memo.txt", "rates.xlsx", "safety_brief.pptx"}
at.run(timeout=120)
body = md_text(at)
out["steps"]["indexed_list_shows_all_3"] = all(
    f in body for f in ["memo.txt", "rates.xlsx", "safety_brief.pptx"])
print("indexed list:", out["steps"]["indexed_list_shows_all_3"])

# Query flow (selectbox default model; streams a real Ollama answer).
at.text_input(key="query_input").set_value("When is the canteen open at midday?").run(timeout=30)
ask = [b for b in at.button if "Query" in (b.label or "")]
assert ask, "query button not found"
ask[0].click().run(timeout=300)
body = md_text(at)
out["steps"]["answer_contains_fact"] = "11:30" in body
out["steps"]["citations_rendered"] = "memo.txt" in body
out["steps"]["no_think_leak"] = "<think" not in body.lower() and "thinking" not in body.lower().replace(
    "reasoning trace is intentionally hidden", "")
out["steps"]["query_exception"] = bool(at.exception)
out["steps"]["query_exceptions"] = [str(getattr(e, "value", e))[:300] for e in (at.exception or [])]
print("answer fact:", out["steps"]["answer_contains_fact"],
      "| citations:", out["steps"]["citations_rendered"],
      "| think-leak:", not out["steps"]["no_think_leak"],
      "| exception:", out["steps"]["query_exception"])

# Delete one file via its UI button.
dels = [b for b in at.button if (b.key or "").startswith("del_")]
out["steps"]["delete_buttons_found"] = len(dels)
dels[0].click().run(timeout=120)
body = md_text(at)
gone = dels[0].key.replace("del_", "")
out["steps"]["deleted_file"] = gone
out["steps"]["deleted_gone_from_list"] = f"`{gone}`" not in body
out["steps"]["docs_after_delete"] = ingest.list_documents()
print("deleted:", gone, "| gone from list:", out["steps"]["deleted_gone_from_list"],
      "| remaining:", out["steps"]["docs_after_delete"])

# Reset workspace via UI button.
reset = [b for b in at.button if "Reset" in (b.label or "")]
assert reset, "reset button not found"
reset[0].click().run(timeout=120)
body = md_text(at) + "\n".join(i.value for i in at.info)
out["steps"]["reset_empty_state"] = "Workspace is empty" in body
out["steps"]["docs_after_reset"] = ingest.list_documents()
print("reset empty:", out["steps"]["reset_empty_state"],
      "| docs:", out["steps"]["docs_after_reset"])

with open(RESULTS, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print("saved", RESULTS)
