import os
import time
import threading
import requests
import streamlit as st
import tempfile
import chromadb
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Import our custom backend modules
from ingest import (ingest_file, remove_document, list_documents,
                    COLLECTION_NAME, CHROMA_DB_PATH, EMBEDDING_MODEL_NAME,
                    filter_new_uploads, prune_removed_files,
                    mark_upload_processed, clear_removal_state)
from extractors import supported_extensions, UnsupportedFormatError, ExtractionError
from retrieve import initialize_retrieval_components, retrieve, retrieve_formulas, RERANKER_MODEL_NAME
from answer import (answer_question, is_numerical_question, build_context_string,
                    format_citations, generate_answer_stream, location_label,
                    OLLAMA_HOST, OLLAMA_MODEL, FALLBACK_MODEL, NUM_CTX)

def _warmup_async(model_name):
    """Load the model into Ollama VRAM without blocking the UI thread.

    Previously the sidebar blocked on a spinner (up to 180s) before the user
    could upload documents or ask anything. The thread only warms Ollama's
    server-side state; completion is detected on the main thread via /api/ps.
    """
    try:
        requests.post(f"{OLLAMA_HOST}/api/generate", json={
            "model": model_name,
            "prompt": "",
            "stream": False,
            "options": {"num_ctx": NUM_CTX}
        }, timeout=170)
    except Exception:
        pass

# Configure the Streamlit page
st.set_page_config(
    page_title="Predator RAG - Local Document Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling via markdown injection
st.markdown("""
    <style>
        /* General styling */
        .main {
            background-color: #0b0f19;
            color: #f1f5f9;
            font-family: 'Inter', sans-serif;
        }
        /* Custom sidebar and widgets styling */
        section[data-testid="stSidebar"] {
            background-color: #111827;
            border-right: 1px solid #1f2937;
        }
        /* Gradient header text */
        .gradient-text {
            background: linear-gradient(135deg, #38bdf8 0%, #a855f7 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            font-size: 2.8rem;
            margin-bottom: 0.2rem;
        }
        /* Premium cards */
        .metric-card {
            background: rgba(30, 41, 59, 0.5);
            border: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 12px;
            padding: 1rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            backdrop-filter: blur(10px);
        }
        .metric-card h4 {
            margin: 0;
            color: #94a3b8;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .metric-card p {
            margin: 0.5rem 0 0 0;
            font-size: 1.5rem;
            font-weight: 700;
            color: #38bdf8;
        }
        /* Success/Status badges */
        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .status-badge.online {
            background-color: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        .status-badge.offline {
            background-color: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
    </style>
""", unsafe_allow_html=True)

# Initialize Session State
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()
if "removed_files" not in st.session_state:
    # Documents removed via their workspace ✖ button while their uploader
    # chip still exists; suppresses instant re-indexing (see ingest.py
    # filter_new_uploads). Codec: name-keyed, cleared on Reset/re-ingest.
    st.session_state.removed_files = set()
if "selected_model" not in st.session_state:
    st.session_state.selected_model = OLLAMA_MODEL
if "warmed_up_models" not in st.session_state:
    st.session_state.warmed_up_models = set()

if "warming_model" not in st.session_state:
    st.session_state.warming_model = None
if "clean_started" not in st.session_state:
    # 5. Clean Startup: reset the app's OWN workspace collection on first
    # app launch (intentional lifecycle: the workspace is rebuilt from
    # uploaded files each session; embeddings are served from ./embed_cache
    # for unchanged files, see ingest.py). Foreign collections sharing the
    # same Chroma directory are never touched here.
    try:
        db_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        if COLLECTION_NAME in [c.name for c in db_client.list_collections()]:
            db_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    st.session_state.clean_started = True
    st.session_state.processed_files = set()
    st.session_state.removed_files = set()

# Load current documents count from ChromaDB
db_count = 0
db_connected = False
try:
    db_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    if COLLECTION_NAME in [c.name for c in db_client.list_collections()]:
        coll = db_client.get_collection(COLLECTION_NAME)
        db_count = coll.count()
        db_connected = True
        
        # Load unique files from collection metadata
        res = coll.get(include=["metadatas"])
        if res and res["metadatas"]:
            unique_files = {m["file"] for m in res["metadatas"] if "file" in m}
            st.session_state.processed_files = unique_files
except Exception as e:
    pass

# Verify Ollama service and get list of models
ollama_status = "offline"
ollama_models = []
loaded_models = []
try:
    resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=1.0)
    if resp.ok:
        ollama_status = "online"
        ollama_models = [m["name"] for m in resp.json().get("models", [])]
        
    resp_ps = requests.get(f"{OLLAMA_HOST}/api/ps", timeout=1.0)
    if resp_ps.ok:
        loaded_models = [m["name"] for m in resp_ps.json().get("models", [])]
except Exception:
    pass

if not ollama_models:
    # Offline fallback offers the default plus the retained fallback model.
    ollama_models = [OLLAMA_MODEL] if OLLAMA_MODEL == FALLBACK_MODEL else [OLLAMA_MODEL, FALLBACK_MODEL]

# =====================================================
# SIDEBAR / SETTINGS & STATUS
# =====================================================
with st.sidebar:
    st.image("https://img.icons8.com/neon/96/graduation-cap.png", width=64)
    st.markdown("<h2 style='margin-top: 0;'>Predator RAG Core</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    st.subheader("Model Configuration")
    # Model Selector dropdown
    selected_model = st.selectbox(
        "Active LLM Model:",
        options=ollama_models,
        index=ollama_models.index(st.session_state.selected_model) if st.session_state.selected_model in ollama_models else 0
    )
    
    # Model change logic: unload old, prompt reload of new
    if selected_model != st.session_state.selected_model:
        old_model = st.session_state.selected_model
        try:
            # Unload old model
            requests.post(f"{OLLAMA_HOST}/api/generate", json={
                "model": old_model,
                "keep_alive": 0,
                "prompt": "",
                "stream": False
            }, timeout=5)
        except Exception:
            pass
        st.session_state.selected_model = selected_model
        st.rerun()

    # Dynamic Warmup on app start or model switch (non-blocking: the model
    # loads in a background thread while the user uploads PDFs; completion
    # is detected via /api/ps on each rerun. Measured cold load ~5s for
    # llama3.1:8b, ~25s for qwen3:8b; blocking the whole UI on it wasted the
    # entire upload window.)
    if st.session_state.selected_model in loaded_models:
        st.session_state.warmed_up_models.add(st.session_state.selected_model)
        st.session_state.warming_model = None
    if st.session_state.selected_model not in st.session_state.warmed_up_models:
        if st.session_state.warming_model != st.session_state.selected_model:
            st.session_state.warming_model = st.session_state.selected_model
            threading.Thread(target=_warmup_async,
                             args=(st.session_state.selected_model,),
                             daemon=True).start()
        st.caption("⏳ Loading model into VRAM in the background — you can upload documents meanwhile.")

    st.markdown("---")
    st.subheader("System Status")
    
    # Ollama Status
    if ollama_status == "online":
        is_loaded = any(st.session_state.selected_model in m or m in st.session_state.selected_model for m in loaded_models)
        if is_loaded:
            st.markdown(f"🤖 **Ollama LLM**: <span class='status-badge online'>🟢 Active & Loaded (VRAM)</span>", unsafe_allow_html=True)
            st.caption(f"Model: `{st.session_state.selected_model}` (Full GPU offload, CUDA)")
        else:
            st.markdown(f"🤖 **Ollama LLM**: <span class='status-badge online'>🟡 Online (Ready to load)</span>", unsafe_allow_html=True)
            st.caption(f"Selected: `{st.session_state.selected_model}`")
    else:
        st.markdown(f"🤖 **Ollama LLM**: <span class='status-badge offline'>🔴 Offline</span>", unsafe_allow_html=True)
        st.caption("Verify native Windows Ollama service is running on port 11434.")
        
    # ChromaDB Status
    if db_connected:
        st.markdown(f"🗄️ **ChromaDB**: <span class='status-badge online'>🟢 Embedded</span>", unsafe_allow_html=True)
        st.caption(f"Indexed Chunks: `{db_count}`")
    else:
        st.markdown(f"🗄️ **ChromaDB**: <span class='status-badge offline'>🔴 Disconnected</span>", unsafe_allow_html=True)
        
    st.markdown("---")
    st.subheader("Compute Engines")
    st.info(f"💾 **Embeddings (GPU/CPU)**:\n`{EMBEDDING_MODEL_NAME}`\n\n🔍 **Reranker (GPU/CPU)**:\n`{RERANKER_MODEL_NAME}`")
    st.caption("Documents are parsed first, then the embedding model is loaded onto GPU (CUDA) if available. Falls back to CPU automatically.")
 
    st.markdown("---")
    if st.button("🗑️ Reset Database & Cache", use_container_width=True, type="secondary"):
        try:
            db_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            db_client.delete_collection(COLLECTION_NAME)
            clear_removal_state(
                st.session_state.processed_files,
                st.session_state.removed_files)
            st.session_state.warmed_up_models.clear()
            st.session_state.warming_model = None
            st.success("Database wiped successfully!")
            time.sleep(1.0)
            st.rerun()
        except Exception as e:
            st.error(f"Error resetting database: {e}")
 
# =====================================================
# MAIN USER INTERFACE
# =====================================================
st.markdown("<div class='gradient-text'>Predator RAG Assistant</div>", unsafe_allow_html=True)
st.markdown("##### Local, private Q&A over your own documents (PDF, Word, PowerPoint, Excel, text)")
st.write("---")
 
# Layout: Ingestion column & Question answering column
col_ingest, col_qa = st.columns([1, 2], gap="large")
 
with col_ingest:
    st.subheader("📄 Knowledge Ingestion")
    st.write("Upload your own documents to build a local searchable workspace. "
             f"Supported: `{', '.join(supported_extensions())}`.")
    st.caption("Workspace starts clean; files are indexed only when you upload them. "
               "Originals are never deleted by Reset.")

    uploaded_files = st.file_uploader(
        "Choose documents",
        type=[e.lstrip(".") for e in supported_extensions()],
        accept_multiple_files=True
    )

    if uploaded_files:
        held_names = [f.name for f in uploaded_files]
        # Release blocks for chips the user has removed, then compute the
        # to-process list honoring removed_files (delete ✖ guard).
        st.session_state.removed_files = prune_removed_files(
            st.session_state.removed_files, held_names)
        new_names = set(filter_new_uploads(
            held_names,
            st.session_state.processed_files,
            st.session_state.removed_files))
        new_files = [f for f in uploaded_files if f.name in new_names]
        if new_files:
            progress_bar = st.progress(0)
            for idx, f in enumerate(new_files):
                st.info(f"Processing '{f.name}'...")
                suffix = os.path.splitext(f.name)[1].lower() or ".tmp"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(f.getvalue())
                    tmp_path = tmp.name

                try:
                    is_first = (db_count == 0 and idx == 0)
                    ingest_file(tmp_path, recreate=is_first, original_filename=f.name)
                    mark_upload_processed(f.name,
                                          st.session_state.processed_files,
                                          st.session_state.removed_files)
                except (UnsupportedFormatError, ExtractionError, OSError) as e:
                    st.error(f"Skipped {f.name}: {e}")
                except Exception as e:
                    st.error(f"Error indexing {f.name}: {e}")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                progress_bar.progress((idx + 1) / len(new_files))
            st.success("Ingestion complete! (Unsupported files were skipped, the rest is searchable.)")
            time.sleep(1.0)
            st.rerun()

    # List uploaded documents with per-file removal
    if st.session_state.processed_files:
        st.write("📁 **Indexed Files:**")
        for f in sorted(list(st.session_state.processed_files)):
            col_name, col_del = st.columns([4, 1])
            with col_name:
                st.markdown(f"- `{f}`")
            with col_del:
                if st.button("✖", key=f"del_{f}", help=f"Remove {f} from workspace"):
                    try:
                        remove_document(f)
                    except Exception as e:
                        st.error(f"Error removing {f}: {e}")
                    st.session_state.processed_files.discard(f)
                    # Mark as removed so the persistent uploader chip does
                    # not silently re-index this document on the next rerun.
                    # NOTE: `f` here is the filename string (loop over
                    # processed_files), not the uploader File object.
                    st.session_state.removed_files.add(f)
                    try:
                        initialize_retrieval_components()
                    except Exception:
                        pass
                    st.rerun()
    else:
        st.info("Workspace is empty. Upload one or more supported documents to start asking questions.")
 
with col_qa:
    st.subheader("💬 Ask Your Question")
    st.write("Ask factual, summary, comparison, or extraction questions about the indexed documents. "
             "Answers cite their sources; unsupported questions are declined honestly.")

    question = st.text_input(
        "Enter question here:",
        placeholder="e.g. What is the approved budget for Project Zephyr?",
        key="query_input"
    )
    
    ask_btn = st.button("🔍 Query System", type="primary", use_container_width=True)
    
    if ask_btn:
        if not question.strip():
            st.warning("Please enter a question.")
        elif not st.session_state.processed_files:
            st.warning("Workspace is empty — upload at least one supported document before asking questions.")
        else:
            with st.spinner("Analyzing question and retrieving context..."):
                try:
                    # Retrieval first (fast: ~50-90ms), then stream the answer
                    # token-by-token so the first words appear in ~1s instead
                    # of after the full 4-8s generation.
                    t0 = time.perf_counter()
                    is_num = is_numerical_question(question)
                    chunks = retrieve(question, limit=6)
                    formulas = retrieve_formulas(question, limit=3) if is_num else None
                    retrieval_latency = time.perf_counter() - t0
                    if not chunks:
                        st.warning("No relevant information found in the indexed materials.")
                    else:
                        context = build_context_string(chunks, formulas)
                        st.markdown("### 💡 Answer:")
                        t1 = time.perf_counter()
                        full_text = st.write_stream(generate_answer_stream(
                            question, context, is_num,
                            st.session_state.selected_model)) or ""
                        gen_latency = time.perf_counter() - t1
                        if not full_text.strip():
                            # Thinking stays enabled server-side, but only the
                            # final `response` field is ever streamed above; an
                            # empty stream means no usable final answer (never
                            # show the hidden reasoning trace instead).
                            st.warning(
                                "The model did not return a final answer for "
                                "this question. Long derivations sometimes need "
                                "a second attempt.")
                            col_retry, col_fb = st.columns(2)
                            with col_retry:
                                if st.button("🔁 Retry query",
                                             use_container_width=True):
                                    st.rerun()
                            with col_fb:
                                if st.button("🦙 Retry with llama3.1:8b fallback",
                                             use_container_width=True):
                                    st.session_state.selected_model = FALLBACK_MODEL
                                    st.rerun()
                        else:
                            citations = format_citations(chunks)

                            # Sources
                            st.markdown("### 📌 Sources Cited:")
                            if citations:
                                for cit in citations:
                                    st.markdown(cit)
                            else:
                                st.info("No explicit source sections were cited for this answer.")

                            st.write("---")

                            # Diagnostics metrics
                            col_type, col_lat, col_lat_r, col_lat_g = st.columns(4)
                            with col_type:
                                st.metric("Question Type", "NUMERICAL" if is_num else "THEORY")
                            with col_lat:
                                st.metric("Total Latency", f"{retrieval_latency + gen_latency:.2f} s")
                            with col_lat_r:
                                st.metric("Retrieval Latency", f"{retrieval_latency:.2f} s")
                            with col_lat_g:
                                st.metric("LLM Gen Latency", f"{gen_latency:.2f} s")

                            # Retrieval diagnostics dropdown (RRF fusion; the
                            # cross-encoder reranker is intentionally disabled —
                            # measured +1.5s latency and -10% recall on CPU).
                            # NOTE: only retrieved workspace chunks are shown here;
                            # the model's private reasoning trace is never logged
                            # or displayed.
                            with st.expander("📊 Retrieval Diagnostics (RRF fusion)"):
                                st.markdown("#### Top Retrieved Chunks (RRF-fused)")
                                for idx, hit in enumerate(chunks, 1):
                                    meta = hit["metadata"]
                                    st.markdown(f"**Chunk #{idx}** | File: `{meta.get('file', '?')}` | Location: `{location_label(meta)}` | Type: `{meta.get('type', 'text')}`")
                                    st.markdown(f"* RRF Score: `{hit.get('rrf_score', 0.0):.4f}`")
                                    st.text_area(f"Content (Chunk #{idx})", value=hit["text"], height=120, key=f"chunk_text_{idx}")
                            
                except Exception as e:
                    st.error(f"Execution failed: {e}")
                    st.exception(e)
