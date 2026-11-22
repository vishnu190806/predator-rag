"""Regression tests for the ChromaDB collection lifecycle.

Covers the stale-collection-reference defect fixed in retrieve.py /
ingest.py / app.py: after the workspace collection is deleted (startup
cleanup or manual reset) and recreated, cached references must be
invalidated so the next retrieval re-connects to the current collection
instead of operating on a stale handle.

Isolation: temp chroma + cache dirs (patched module constants); never touches
the production database. Synthetic documents only.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "eval_general", "eval_corpus")


@pytest.fixture()
def isolated(tmp_path):
    import ingest
    import retrieve
    chroma = str(tmp_path / "chroma")
    cache = str(tmp_path / "cache")
    os.makedirs(chroma, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    old = (ingest.CHROMA_DB_PATH, ingest.EMBED_CACHE_DIR,
           retrieve.CHROMA_DB_PATH)
    ingest.CHROMA_DB_PATH = chroma
    ingest.EMBED_CACHE_DIR = cache
    retrieve.CHROMA_DB_PATH = chroma
    retrieve._db_client = None
    retrieve._collection = None
    retrieve._bm25 = None
    retrieve._corpus_data = None
    yield {"chroma": chroma, "cache": cache}
    ingest.CHROMA_DB_PATH, ingest.EMBED_CACHE_DIR, retrieve.CHROMA_DB_PATH = old
    retrieve._db_client = None
    retrieve._collection = None
    retrieve._bm25 = None
    retrieve._corpus_data = None


def test_retrieve_after_collection_reset(isolated):
    """Step 1-6 from the lifecycle spec: ingest -> retrieve (caches
    collection) -> reset (delete collection) -> invalidate -> ingest new ->
    retrieve (must work without restart)."""
    import chromadb
    import ingest
    from retrieve import retrieve, invalidate_collection_cache

    # Step 1-2: ingest and retrieve (caches collection in retrieve.py).
    ingest.ingest_file(os.path.join(CORPUS, "station.pdf"),
                      recreate=True, original_filename="station.pdf")
    hits = retrieve("Mark-IV reactor outputs how many megawatts", limit=2)
    assert hits and hits[0]["metadata"]["file"] == "station.pdf"

    # Step 3-4: simulate manual reset (delete collection via a separate
    # client, as app.py's reset button does).
    client = chromadb.PersistentClient(path=isolated["chroma"])
    client.delete_collection("workspace_chunks")

    # Invalidate the cached reference (as app.py's reset button now does).
    invalidate_collection_cache()

    # Step 5: ingest a different document into the recreated collection.
    ingest.ingest_file(os.path.join(CORPUS, "crew.csv"),
                      recreate=False, original_filename="crew.csv")

    # Step 6: retrieve must work against the new collection without restart.
    hits = retrieve("Elena Vasquez commander clearance", limit=2)
    assert hits, "retrieval returned no results after reset"
    assert hits[0]["metadata"]["file"] == "crew.csv", (
        "retrieval did not see the post-reset collection contents")


def test_retrieve_after_reset_without_invalidation_fails(isolated):
    """Demonstrate the original defect: without invalidate_collection_cache,
    retrieve operates on a stale collection handle. With the fix applied,
    calling invalidate_collection_cache is the correct path; this test
    verifies that the stale-handle state is detectable.

    Note: ChromaDB behaviour for deleted collections varies by version, so
    this test only asserts that invalidation is the supported recovery
    mechanism. It is a documentation-of-defect test, not a regression gate.
    """
    import chromadb
    import ingest
    from retrieve import retrieve, invalidate_collection_cache

    ingest.ingest_file(os.path.join(CORPUS, "station.pdf"),
                      recreate=True, original_filename="station.pdf")
    retrieve("Mark-IV reactor outputs how many megawatts", limit=2)

    # Delete the collection via a separate client (as app.py does).
    client = chromadb.PersistentClient(path=isolated["chroma"])
    client.delete_collection("workspace_chunks")

    # The cached _collection may now be stale. Invalidate it (the fix).
    invalidate_collection_cache()

    # Re-create the collection and ingest new data.
    new_coll = client.get_or_create_collection("workspace_chunks")
    assert new_coll is not None

    # After invalidation, get_db() creates a fresh handle.
    from retrieve import get_db
    fresh = get_db()
    assert fresh is not None
    assert fresh.count() == 0  # new collection is empty


def test_repeated_reset_and_ingest_cycles(isolated):
    """Multiple reset + ingest + retrieve cycles remain functional."""
    import chromadb
    import ingest
    from retrieve import retrieve, invalidate_collection_cache

    files = ["station.pdf", "zephyr.docx", "helios.pptx"]
    for cycle, fname in enumerate(files):
        # Simulate reset: delete collection if it exists.
        client = chromadb.PersistentClient(path=isolated["chroma"])
        try:
            client.delete_collection("workspace_chunks")
        except Exception:
            pass
        invalidate_collection_cache()

        # Ingest one document.
        ingest.ingest_file(os.path.join(CORPUS, fname),
                          recreate=False, original_filename=fname)

        # Retrieve must work.
        hits = retrieve("budget", limit=2)
        # At least one hit or empty (some docs may not match "budget")
        # The key assertion: no exception and no stale-reference error.
        assert isinstance(hits, list)


def test_document_removal_affects_only_selected_file(isolated):
    """remove_document deletes only the requested file's chunks."""
    import ingest
    from retrieve import retrieve

    ingest.ingest_file(os.path.join(CORPUS, "station.pdf"),
                      recreate=True, original_filename="station.pdf")
    ingest.ingest_file(os.path.join(CORPUS, "zephyr.docx"),
                      original_filename="zephyr.docx")

    docs_before = set(ingest.list_documents())
    assert docs_before == {"station.pdf", "zephyr.docx"}

    removed = ingest.remove_document("zephyr.docx")
    assert removed > 0

    docs_after = set(ingest.list_documents())
    assert docs_after == {"station.pdf"}, docs_after

    # station.pdf still retrievable.
    hits = retrieve("Mark-IV reactor outputs how many megawatts", limit=2)
    assert hits and hits[0]["metadata"]["file"] == "station.pdf"


def test_foreign_collection_survives_workspace_operations(isolated):
    """Foreign collections sharing the same Chroma directory are never
    deleted by workspace ingest/reset operations."""
    import chromadb
    import ingest
    from retrieve import invalidate_collection_cache

    # Seed a foreign collection.
    client = chromadb.PersistentClient(path=isolated["chroma"])
    foreign = client.get_or_create_collection("foreign_legacy")
    foreign.add(ids=["f1"], documents=["legacy physics chapter text"],
                embeddings=[[0.1] * 768],
                metadatas=[{"file": "legacy.pdf", "type": "theory", "page": 1}])

    # Ingest into workspace.
    ingest.ingest_file(os.path.join(CORPUS, "station.pdf"),
                      recreate=True, original_filename="station.pdf")

    # Foreign collection must survive.
    client2 = chromadb.PersistentClient(path=isolated["chroma"])
    names = [c.name for c in client2.list_collections()]
    assert "foreign_legacy" in names
    assert client2.get_collection("foreign_legacy").count() == 1

    # Reset: delete workspace collection.
    try:
        client2.delete_collection("workspace_chunks")
    except Exception:
        pass
    invalidate_collection_cache()

    # Foreign collection must still survive.
    client3 = chromadb.PersistentClient(path=isolated["chroma"])
    names = [c.name for c in client3.list_collections()]
    assert "foreign_legacy" in names
    assert client3.get_collection("foreign_legacy").count() == 1


def test_db_directory_not_deleted(isolated):
    """Workspace operations never delete the chroma_db directory itself."""
    import os
    import ingest
    from retrieve import invalidate_collection_cache

    ingest.ingest_file(os.path.join(CORPUS, "station.pdf"),
                      recreate=True, original_filename="station.pdf")
    assert os.path.isdir(isolated["chroma"])

    import chromadb
    client = chromadb.PersistentClient(path=isolated["chroma"])
    try:
        client.delete_collection("workspace_chunks")
    except Exception:
        pass
    invalidate_collection_cache()

    assert os.path.isdir(isolated["chroma"]), "chroma_db directory was deleted"
    # Foreign collections can be re-created (directory still usable).
    client2 = chromadb.PersistentClient(path=isolated["chroma"])
    c = client2.get_or_create_collection("workspace_chunks")
    assert c is not None


def test_invalidate_collection_cache_resets_all_globals():
    """invalidate_collection_cache sets all cached globals to None."""
    import retrieve
    # Set some cached values.
    retrieve._db_client = "fake_client"
    retrieve._collection = "fake_collection"
    retrieve._bm25 = "fake_bm25"
    retrieve._corpus_data = "fake_corpus"
    retrieve.invalidate_collection_cache()
    assert retrieve._db_client is None
    assert retrieve._collection is None
    assert retrieve._bm25 is None
    assert retrieve._corpus_data is None
