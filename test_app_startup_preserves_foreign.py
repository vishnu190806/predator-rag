"""Regression test: app startup must not delete collections it does not own.

Pre-fix defect (app.py "clean_started" block): the first Streamlit session
load deleted EVERY collection in ./chroma_db, silently destroying foreign
collections the app neither owns nor reads -- concretely the legacy
`textbook_chunks` physics index (~7,868 chunks, pre-cache-era artifact) would
be wiped on the next app launch. The documented intentional lifecycle is a
clean app WORKSPACE (`workspace_chunks`) per session, not deletion of
unrelated collections sharing the same Chroma directory.

Isolated: seeds and inspects a throwaway ./chroma_db under pytest tmp_path;
never touches the production database. Mirrors the AppTest harness pattern of
eval_realworld/ui_realworld.py. NOTE: executing this test briefly boots the
real app, which may auto-warm the selected Ollama model -- do not run while a
model-heavy job is in progress.

Run: python -m pytest test_app_startup_preserves_foreign.py -q
"""
import os

import pytest


@pytest.fixture()
def seeded_chroma(tmp_path, monkeypatch):
    """Isolated cwd + seeded Chroma directory with foreign + owned data.

    chromadb caches client instances by the path STRING, so a relative
    "./chroma_db" would alias DBs across tests in one pytest process. The app
    reads CHROMA_DB_PATH from the ingest module at exec time, so the module
    constant is pointed at this test's absolute tmp path (auto-restored by
    monkeypatch) instead of relying on cwd resolution.
    """
    import sys
    import chromadb
    import ingest as ingest_mod
    import retrieve as retrieve_mod

    work = tmp_path / "appboot"
    work.mkdir()
    monkeypatch.chdir(work)

    path = str(work / "chroma_db")
    monkeypatch.setattr(ingest_mod, "CHROMA_DB_PATH", path)
    monkeypatch.setattr(retrieve_mod, "CHROMA_DB_PATH", path)

    client = chromadb.PersistentClient(path=path)

    foreign = client.get_or_create_collection("foreign_legacy")
    foreign.add(ids=["f1"], documents=["legacy physics chapter text"],
                embeddings=[[0.1] * 8],
                metadatas=[{"file": "legacy.pdf", "type": "theory",
                            "page": 1}])
    owned = client.get_or_create_collection("workspace_chunks")
    owned.add(ids=["w1"], documents=["stale workspace chunk"],
              embeddings=[[0.1] * 8],
              metadatas=[{"file": "old.pdf", "type": "theory", "page": 2}])
    return work, path


def _boot_app():
    app_root = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "app.py")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(app_root, default_timeout=90)
    at.run()
    return at


def test_boot_preserves_foreign_collections(seeded_chroma):
    """Foreign collections survive app boot; owned workspace is reset."""
    import chromadb

    work, path = seeded_chroma
    _boot_app()

    client = chromadb.PersistentClient(path=path)
    names = [c.name for c in client.list_collections()]
    assert "foreign_legacy" in names, (
        "app boot deleted a collection it does not own (data loss)")
    assert client.get_collection("foreign_legacy").count() == 1, (
        "foreign collection documents were deleted by app boot")


def test_boot_resets_only_own_workspace(seeded_chroma):
    """Documented per-session lifecycle: app's own workspace is cleaned."""
    import chromadb

    work, path = seeded_chroma
    _boot_app()

    client = chromadb.PersistentClient(path=path)
    names = [c.name for c in client.list_collections()]
    if "workspace_chunks" in names:
        assert client.get_collection("workspace_chunks").count() == 0, (
            "failed to reset the app's own workspace on first launch")
    # workspace_chunks absent entirely is equally valid for a clean session.
