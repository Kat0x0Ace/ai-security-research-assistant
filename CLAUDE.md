# RAG Agent — AI Security Research Assistant

## What this is

A local, private RAG assistant that answers questions about AI security with citations, or an honest "I don't know". Embeddings, vector search and the LLM all run on the user's machine: no API keys, no data leaves it. It's a **portfolio project**, so the README, tests and measured results matter as much as the features.

Core loop: ask a question → get a cited answer in a few seconds → open the sources to check them.

> v1 (Gemini Embedding 2 + Pinecone + OpenRouter, multimodal plan) was replaced by this fully local v2. The old multimodal phases are dropped, not pending.

## Stack

- **Embeddings**: sentence-transformers `all-MiniLM-L6-v2` (384-dim), local CPU
- **Vector DB**: ChromaDB persistent client (`cache/chroma`), cosine
- **LLM**: Ollama `llama3.1:8b` through its OpenAI-compatible endpoint (swappable via `.env`)
- **UI**: Streamlit 1.66, custom "analyst's dossier" theme, fonts self-hosted in `static/fonts`
- **Tests**: pytest, retrieval eval, live prompt-injection red-team; GitHub Actions CI
- **Lang**: Python 3.11+ (developed on 3.14, CI on 3.12)

## Architecture in one paragraph

`config.py` holds settings and lazy singletons (embedding model behind a lock, Chroma, Ollama client). `ingest/` loads txt/md/pdf → chunks into single-line word windows → embeds (SQLite cache) → upserts to Chroma. `rag.py` runs a turn: small talk gets a canned reply; otherwise retrieve top-k → refuse if the closest passage is farther than the cutoff → wrap passages as untrusted data → call the LLM (`answer()` or streamed `stream_answer()`) → truncate refuse-then-hallucinate output. `ui/render.py` escapes all untrusted text **first**, then adds citation badges; `ui/sidebar.py` and `ui/knowledge_base.py` build the sidebar; `app.py` only wires these together. `warmup.py` loads the embedding model and LLM in the background at launch.

## Project layout

```
app.py                  # Streamlit entry point (wiring only)
rag.py                  # small talk -> retrieve -> refusal gate -> cited answer (sync + streamed)
config.py               # .env settings + lazy singletons
warmup.py               # background warm-up at launch
ingest/                 # loader, chunker, embedder, cache, pipeline
ui/                     # render.py (escape-first HTML), sidebar.py, knowledge_base.py, styles.css
.streamlit/config.toml  # theme + font faces + static serving
static/fonts/           # self-hosted fonts + their OFL licenses
evals/                  # run_eval.py (retrieval, CI gate), injection_eval.py (live red-team) + reports
tests/                  # unit tests (no LLM needed)
scripts/                # take_screenshots.py (Playwright, dev-only)
docs/screenshots/       # README images
mockups/                # approved design mockups
data/sample-corpus/     # AI-security sample documents
```

## Status

- ✅ Local v2 stack, text ingest (txt/md/pdf), chat with citations + refusal
- ✅ UI redesign, streaming, warm-up, small-talk handling, calibrated refusal cutoff
- ✅ Prompt-injection hardening, CI, README with screenshots + measured results, MIT license
- ⏳ Stronger red-team (poisoned passage ranked first; less safety-tuned target model)
- ⏳ Conversation memory (rewrite follow-ups into standalone questions)
- ⏳ Hybrid search (BM25 + vectors) / re-ranking, Docker

## How to run

Needs Python 3.11+ and [Ollama](https://ollama.com) with `ollama pull llama3.1:8b`.

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python evals/run_eval.py --reingest   # first time: builds the index
streamlit run app.py
```

**Mac**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python evals/run_eval.py --reingest
streamlit run app.py
```

**Tests and evals:**
- `pytest -q`
- `python evals/run_eval.py` (must stay ≥ 80%)
- `python evals/injection_eval.py [--control]` (needs Ollama)

**Screenshots:** `pip install playwright`, then `python scripts/take_screenshots.py`. It uses Edge on Windows; on Mac run `playwright install chromium` and pass `--browser chromium`.

## Key settings (`.env`, see `.env.example`)

- `RETRIEVAL_MAX_DISTANCE=0.75`: calibrated. Eval questions score 0.25–0.69 and off-topic messages 0.84–0.96. Re-measure if the corpus or embedding model changes.
- `LLM_TOP_K=3`: was 5. Reading 5 passages roughly tripled latency with no quality gain.
- `OLLAMA_MODEL=llama3.1:8b`: don't swap to a smaller model without re-running the refusal checks (see lessons).

## Security posture

- No secrets: the stack is keyless. `.env` is still gitignored.
- Retrieved passages are wrapped in `<untrusted>` tags. Delimiters inside documents are neutralised (`rag._neutralize`).
- All model output, excerpts and titles are HTML-escaped before display. Markdown links and images never render (exfiltration guard).
- Off-topic questions never reach the LLM. Refuse-then-answer output is truncated, including while streaming.
- The live red-team was **inconclusive**: the undefended control resisted too. Don't claim the prompt layer "stops" attacks; the unit tests are the proof.
- **This file is tracked in git:** no personal info, usernames, paths or device details in it or in the session log.

## Lessons learned (so they don't bite twice)

- **Smaller models can break the honesty guarantee.** `llama3.2:3b` refused and then answered from memory anyway. Speed changes need a quality check, not just a timing check.
- **Ollama skips integrated GPUs by default.** Set `OLLAMA_IGPU_ENABLE=1` (and `OLLAMA_KEEP_ALIVE=30m` to avoid reload pauses), then restart Ollama. Check the result with `ollama ps` (PROCESSOR column).
- **Windows Smart App Control can block a freshly installed native wheel once** ("An Application Control policy has blocked this file"). Retrying and restarting Streamlit worked. Don't disable Smart App Control.
- **Chunks are single-line word windows.** Text processing that assumes line breaks (e.g. "drop heading lines") silently breaks. Test with real chunk text.
- **A red-team needs a control run.** Without one, a 100% pass rate says nothing about your defenses.
- **Rendering LLM output as HTML is only safe escape-first.** Never pass model text to `st.markdown` as markdown.

## Session log

### 2026-10-30
- Did: Got the local v2 stack running end to end. Redesigned the UI from an approved mockup: dossier theme, self-hosted fonts, right-aligned user bubbles, citation badges, sources panel with match bars, refusal callout, "Try asking" examples, knowledge-base index, model label, shield favicon. Speed: GPU fix, 3 passages instead of 5, streaming, background warm-up. Answers went from 40–97s to first words in about 3–5s. Added small-talk replies and calibrated the refusal cutoff (1.1 → 0.75), plus truncation of refuse-then-hallucinate output. Security: escape-first rendering, documents can no longer forge the `<untrusted>` wrapper, and a live red-team with an undefended control (result inconclusive, documented honestly). Also added CI, an MIT license, font OFL files, a README rewrite with screenshots and measured results, a screenshot script, and rewrote this CLAUDE.md. 47 tests pass; retrieval eval 96%. Branch `ui-redesign-and-hardening` pushed (3 commits).
- Next: Open the repo's GitHub **Actions** tab, confirm the first CI run on `ui-redesign-and-hardening` is green (fix it if red), then open the PR and merge to `main`.
- Parked: stronger red-team (poisoned passage ranked first; a less safety-tuned target model) · conversation memory (rewrite follow-ups into standalone questions) · hybrid search / re-ranking · Docker · optional "answer in 2–4 sentences" speed tweak (not approved yet) · before making the repo public, re-read this file and git history for personal details · set Ollama up on the Mac too (see Lessons learned).
- Artifacts:
  - Mockups: `mockups/ui-design.html` and `mockups/ui-copy-wireframe.html`. Open with `start mockups\ui-design.html` (Windows) or `open mockups/ui-design.html` (Mac).
  - README screenshots: `docs/screenshots/*.png`. Regenerate with `python scripts/take_screenshots.py`.
  - Red-team reports: `evals/injection_report.md` and `evals/injection_report_control.md`.
- Secrets flagged: none
- Drift check: Stayed on this project the whole session. Scope grew from "how do I run it" into UI redesign, speed and portfolio polish. Every step was approved, and it all served this project's presentation goal.

### 2026-05-26 — Phase 1 (foundation) built

**Done**
- Architecture decided: Gemini Embedding 2 (multimodal, 1536-dim MRL) + Pinecone serverless + OpenRouter, Streamlit chat UI
- Wrote `.env`, `.env.example`, `.gitignore`, `requirements.txt`
- Wrote `config.py` with lazy singletons for Gemini / Pinecone / OpenRouter clients + auto-creating Pinecone index helper
- Wrote `ingest/embedder.py` (`embed_text`, `embed_query`, `embed_file`) with exponential-backoff retry
- Wrote `ingest/cache.py` SQLite-backed embedding cache, keyed by `sha256(model + dim + task_type + content)`
- Wrote this CLAUDE.md

**Next step**
- OBSOLETE (2026-10-30): v1 (API keys, Pinecone) was replaced by the keyless local v2 stack.

**Parked**
- DROPPED (2026-10-30): ffmpeg / video ingestion. The multimodal phases were dropped in v2.
- DONE (2026-10-30): kept Streamlit, now with a custom theme (see `ui/`, `.streamlit/config.toml`). FastAPI + a custom frontend is no longer needed.
