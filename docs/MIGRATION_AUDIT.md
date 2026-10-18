# WSL2 to Windows Native Migration Audit

This document audits the legacy WSL2-based LLM+RAG setup, explaining what components are being replaced, why they are being retired, and how the new native Windows architecture resolves the performance issues.

## Legacy WSL2 Setup Components & Resource Bottlenecks

1. **WSL2 Environment (Ubuntu/Conda `rag_v2`)**
   - **What's being killed**: The entire execution of python scripts (`app.py`, `ingest.py`, etc.) within the WSL2 environment.
   - **Why**: WSL2 maps the Windows filesystem (e.g. `/mnt/c/`) through a virtualization layer 9P, which causes extreme disk I/O sluggishness when loading large datasets or reading SQLite files. It also runs a dynamic memory footprint (`VmmemWSL`) that frequently hogged up to 8–10GB of RAM without releasing it back to the Windows host, leaving less than 6GB for Windows itself.

2. **Ollama Network Proxy (`ollama_proxy.py`)**
   - **What's being killed**: The Windows python proxy script that forwarded ports from WSL2 to the Windows Ollama instance.
   - **Why**: Redundant networking layer. By running Streamlit and Python natively on Windows, the RAG code can communicate directly with the local Ollama instance on `http://127.0.0.1:11434` with zero network bridging latency.

3. **Qdrant Vector DB (Disk storage under WSL2 paths)**
   - **What's being killed**: Qdrant local client database running inside the project.
   - **Why**: Qdrant-client in local disk mode has some memory overhead and, when combined with WSL2 filesystem translation, was causing file access lockups and disk thrashing. We are replacing it with **ChromaDB** in persistent, in-process embedded mode. ChromaDB runs purely as an in-memory SQLite wrapper in python, requiring no background service, minimal RAM (<50MB), and native Windows file access speed.

4. **GPU-Local Embeddings (BGE-M3) & Reranker (BGE-Reranker-v2-m3) on CUDA**
   - **What's being killed**: Generating dense/sparse embeddings and reranking on the GPU inside WSL2/Windows.
   - **Why**: Loading both the embedding model and the cross-encoder reranker into GPU VRAM alongside the LLM (Qwen3-8B) was exceeding the RTX 4070's 8GB limit. This forced CUDA to page memory back to system RAM (system paging/shared GPU memory), leading to massive slowdowns (disk thrashing) and making the system sluggish.
   - **Solution**: We migrate embeddings to `BAAI/bge-small-en-v1.5` and reranking to `BAAI/bge-reranker-base`, running **exclusively on the CPU**. This frees up 100% of the 8GB VRAM for the Qwen3 LLM and its KV cache.

## Native Windows Architecture

- **Inference Server**: Native Windows Ollama using standard GPU acceleration (via CUDA).
- **Embeddings & Reranker**: CPU-bound execution using `sentence-transformers` on CPU.
- **Vector DB**: In-process ChromaDB storing vectors at `./chroma_db` (using native Windows NTFS file I/O).
- **Execution**: Native Windows Powershell or Command Prompt running python `app.py`.
