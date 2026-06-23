# RAG Agent — multimodal RAG with Gemini Embedding 2 + Pinecone + OpenRouter

## What this is

A personal multimodal RAG. Drop text, images, and videos in a local folder (or pass URLs), they get embedded with `gemini-embedding-2` and upserted to a single Pinecone index. A Streamlit chat UI lets you ask questions; retrieval hits all modalities at once and an OpenRouter LLM synthesizes the answer.

Why this works now: Gemini Embedding 2 is natively multimodal — text, image, video, and audio share one embedding space. Cross-modal retrieval works out of the box, no CLIP-and-text pairing.

## Stack

- **Embeddings**: Gemini Embedding 2 (`gemini-embedding-2`), MRL-truncated to **1536 dims**
- **Vector DB**: Pinecone serverless (AWS us-east-1), cosine metric
- **LLM**: OpenRouter (default: `anthropic/claude-sonnet-4.6`, swappable via `.env`)
- **UI**: Streamlit chat (will be added in Phase 2)
- **Lang**: Python 3.11+

## Architecture in one paragraph

`config.py` is the single source of truth for env vars and client singletons (Gemini, Pinecone, OpenRouter — all lazy-initialized). `ingest/embedder.py` is the only place that calls Gemini for embeddings. `ingest/cache.py` is a SQLite cache keyed by content hash so re-ingestion is cheap. The ingestion pipeline (Phase 2+) chunks/loads content, embeds it via the cached embedder, and upserts to Pinecone. The RAG layer (Phase 2) embeds the query, retrieves top-k, and calls OpenRouter with the retrieved snippets as context.

## Project layout

```
RAG Agent/
├── .env                  # your real keys (gitignored)
├── .env.example          # placeholders (committed)
├── .gitignore
├── requirements.txt
├── config.py             # env + client singletons
├── ingest/
│   ├── __init__.py
│   ├── embedder.py       # Gemini Embedding 2 wrapper
│   └── cache.py          # SQLite embedding cache
├── data/                 # drop your files here (gitignored)
└── cache/                # SQLite cache (gitignored)
```

Phase 2+ adds `ingest/chunker.py`, `ingest/loader.py`, `ingest/pipeline.py`, `search.py`, `rag.py`, `app.py`.

## Phases (build one at a time)

- ✅ **Phase 1** — Foundation: env, config, embedder, cache, index auto-create
- ⏳ **Phase 2** — Text ingest + chat (text files, retrieval, OpenRouter, Streamlit)
- ⏳ **Phase 3** — Images
- ⏳ **Phase 4** — Video (ffmpeg splitter, ≤110s clips)
- ⏳ **Phase 5** — URLs (with SSRF + MIME guards)
- ⏳ **Phase 6** — Polish

Full plan: `~/.claude/plans/https-blog-google-innovation-and-ai-mode-crystalline-wave.md`

## How to run

```powershell
# One-time setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Fill in your 3 keys in .env (Pinecone, Gemini, OpenRouter)

# Phase 1 connectivity check
python -c "from config import pinecone_index; print(pinecone_index.describe_index_stats())"
```

The connectivity check auto-creates the Pinecone index on first run.

## Security posture (recap)

- `.env` is gitignored; only `.env.example` is committed
- All keys read via env, never hardcoded
- Retrieved content will be wrapped as untrusted data in LLM context (prompt-injection mitigation) — implemented in Phase 2
- URL ingestion will have SSRF guards (private-IP block, scheme allowlist, size cap) — implemented in Phase 5

## Session log

### 2026-05-26 — Phase 1 (foundation) built

**Done**
- Architecture decided: Gemini Embedding 2 (multimodal, 1536-dim MRL) + Pinecone serverless + OpenRouter, Streamlit chat UI
- Wrote `.env`, `.env.example`, `.gitignore`, `requirements.txt`
- Wrote `config.py` with lazy singletons for Gemini / Pinecone / OpenRouter clients + auto-creating Pinecone index helper
- Wrote `ingest/embedder.py` (`embed_text`, `embed_query`, `embed_file`) with exponential-backoff retry
- Wrote `ingest/cache.py` SQLite-backed embedding cache, keyed by `sha256(model + dim + task_type + content)`
- Wrote this CLAUDE.md

**Next step**
- You drop your three API keys into `.env`
- Run the connectivity check: `python -c "from config import pinecone_index; print(pinecone_index.describe_index_stats())"`
- If that prints index stats (likely `{'total_vector_count': 0, ...}`), Phase 1 is done and we move to Phase 2 (text ingest + chat)

**Parked**
- ffmpeg-on-PATH check vs bundling `imageio-ffmpeg` — decide when we get to Phase 4
- Whether to keep Streamlit or upgrade to FastAPI + a polished frontend — defer until the RAG works end-to-end
