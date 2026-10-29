# RAG Research Copilot

A citation-enforcing, refusal-honest RAG assistant that runs **100% locally and for free** — local embeddings, local vector store, local LLM. Your documents never leave your machine.

Ask questions about a document corpus (this repo ships with an AI-security sample corpus; drop your own files into `data/`), and get answers grounded in retrieved sources with `[n]` citations — or a plain refusal when retrieval finds nothing relevant.

## Why this design

The three behaviors that matter here are the ones most tutorials skip:

- **Citation enforcement** — every answer references the source chunks it used, so claims are auditable.
- **Refusal behavior** — if the best retrieval hit is still too distant (cosine distance above a threshold), the copilot says "I don't know" instead of hallucinating. Tested in CI.
- **Untrusted-content wrapping** — retrieved chunks are delimited and passed as data, never as instructions (prompt-injection mitigation, since document corpora are attacker-writable in the general case).

## Stack (free + local)

| Layer | Choice | Runs |
|---|---|---|
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, 384-dim) | local CPU |
| Vector DB | ChromaDB persistent client | local disk |
| LLM | Ollama (`llama3.1:8b` default, swappable) | local |
| UI | Streamlit chat | local |
| Evals + CI | pytest + retrieval eval suite, GitHub Actions | free tier |

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Install Ollama (https://ollama.com) and pull a model:
ollama pull llama3.1:8b

# Ingest the sample corpus (data/) into the local index:
python evals/run_eval.py --reingest --threshold 0.0   # builds index + prints eval report

# Chat:
streamlit run app.py
```

No API keys required. `.env` is optional tuning (see `.env.example`).

## Retrieval eval (the CI gate)

`evals/eval_set.yaml` holds question → expected-source pairs. `evals/run_eval.py` embeds each question, retrieves top-3, and checks the expected source appears. Hit-rate must be ≥ 80% or CI fails. The report lands in `evals/eval_report.md`.

Run locally:

```bash
python evals/run_eval.py            # uses existing index
python evals/run_eval.py --reingest # rebuild index from data/ first
```

## Project layout

```
config.py               # env + lazy singletons (embedder, Chroma, Ollama)
ingest/
  embedder.py           # local embedding wrapper (only place vectors are computed)
  cache.py              # SQLite embedding cache (sha256 model+content keyed)
  chunker.py            # overlapping word-window chunking
  loader.py             # txt/md/pdf -> (source, text)
  pipeline.py           # load -> chunk -> embed -> upsert (idempotent)
rag.py                  # retrieve -> refusal guardrail -> answer with [n] citations
app.py                  # Streamlit chat UI with source display
evals/
  eval_set.yaml         # question/expected-source cases
  run_eval.py           # hit-rate runner + report
tests/                  # chunker, loader, cache, refusal-logic unit tests
data/                   # drop your corpus here (sample-corpus/ ships in repo)
```

## Roadmap

- [x] v2: local stack swap (ChromaDB + sentence-transformers + Ollama)
- [x] v2: text ingest + chat with citations and refusal
- [x] v2: retrieval eval suite + CI gate
- [ ] FastAPI service layer + polished frontend
- [ ] Re-ranking / hybrid search (BM25 + vectors)
- [ ] Multimodal ingestion (images/video) — stretch, carried from v1 plan

## Security posture

- No API keys needed; anything secret stays in `.env` (gitignored)
- Retrieved content wrapped as untrusted data in the LLM context
- Refusal path avoids answering from weak retrieval
- URL ingestion (if added) must include SSRF guards: private-IP block, scheme allowlist, size cap
