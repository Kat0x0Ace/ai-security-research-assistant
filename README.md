# AI Security Research Assistant

A local, private RAG assistant that answers questions about AI security **with citations, or an honest "I don't know"**. Embeddings, vector search and the LLM all run on your own machine. No API keys, and no data leaves your machine.

![Demo: a streamed, cited answer, the sources panel, small talk and a refusal](docs/demo.gif)

*A real recording: the answer streams in with citation badges, the sources open with their match strength, small talk gets a reply without a search, and an off-topic question is refused before it ever reaches the LLM.*

## Built to be trusted

Most RAG demos stop at "it answers". This one focuses on the three behaviours that matter when the answers need to be trusted:

- **Citations on every answer.** Each claim carries a `[n]` badge that maps to the exact passage it came from, with a match-strength bar so you can judge the evidence.
- **Refusal instead of hallucination.** If nothing in the knowledge base is close enough, it says so without calling the LLM. If the model starts to refuse and then keeps going from memory, the extra text is cut before it reaches the screen.
- **Treats documents as hostile.** Retrieved passages are wrapped as untrusted data, documents can't forge the wrapper, and everything the model outputs is HTML-escaped before display. A poisoned document can't inject scripts or exfiltrate data through markdown images.

![Cited answer with sources](docs/screenshots/cited-answer.png)

## Measured, not guessed

Every tuning decision below came from a measurement on this project, not a default.

| Decision | What was measured | Result |
|---|---|---|
| Refusal cutoff = **0.75** cosine distance | All 25 eval questions scored 0.25–0.69; off-topic messages ("thanks", "capital of France", "pizza recipe") scored 0.84–0.96 | The old cutoff (1.1) never triggered, so off-topic chat got answered from random passages. 0.75 sits in the gap. |
| Keep **llama3.1:8b**, reject llama3.2:3b | Same questions on both | The 3B model answered ~2× faster but said "I don't have relevant material" and then **answered from memory anyway**. Speed isn't worth breaking the core guarantee. |
| **3 passages** per question instead of 5 | Timed end to end | 40–97s → 12–20s per answer, same answers and citations |
| Run on the **integrated GPU** | Ollama logs showed it detected the integrated GPU and then skipped it by default | Generation 9 → 18 tokens/s; answers 8–12s |
| **Stream** answers + **warm up** models at launch | Time to first words; first question after launch | First words in ~3–5s. First question after launch 14s+ → 5.4s |
| **Hybrid search** (vectors + BM25) | Retrieval eval, 25 questions | Hit-rate 96% → 100%: the one question pure vectors missed is caught by keyword match |
| **ONNX Runtime** instead of PyTorch | Cosine similarity of new vs. old vectors on every chunk | 1.000000 (identical), with a far smaller install. PyTorch's DLLs can be blocked by Windows application-control policies |
| Refusal gate on the **closest** passage | Real vs. off-topic questions under hybrid retrieval | 0/25 real questions refused, 0/8 off-topic let through. Robust when keyword search ranks a weaker passage first |

Current numbers: **100% retrieval hit-rate** (25/25, with hybrid search), **87 unit tests**, answers start appearing within a few seconds on integrated graphics (no discrete GPU needed).

## Security model

Untrusted content goes through three independent layers:

1. **Prompt layer.** Passages are wrapped in `<untrusted>` tags and the system prompt forbids following instructions inside them. Any `<untrusted`/`</untrusted>` text inside a document is neutralised, so a poisoned document can't close the wrapper early and pose as trusted instructions. *(Unit-tested.)*
2. **Output layer.** Model answers, document excerpts and titles are HTML-escaped **first**. Only then are fixed elements added (citation badges, bold, lists). Raw HTML, `<img onerror>`, links and markdown images never render, which closes the classic exfiltration-via-image-URL trick. *(Unit-tested.)*
3. **Refusal layer.** Low-relevance questions never reach the LLM, and refuse-then-hallucinate output is truncated. *(Unit-tested.)*

**Live red-team** ([`evals/injection_eval.py --matrix`](evals/injection_eval.py)): 8 attacks (instruction override, delimiter escape, fake authority, image exfiltration, system-prompt leak, three kinds of fact/link poisoning), 3 runs each. Every cell is compared against a **control**: the same attacks against a naive, undefended RAG prompt. The poisoned passage is placed either second or **first** (attackers aim for the top retrieval slot). A weaker model is included to stress the defenses. "Fooled" means the answer carried the attacker's canary, URL or leaked system-prompt text.

| Target model | Poisoned passage | Defended | Control (no defenses) |
|---|---|---|---|
| llama3.1:8b | ranked second | 0/24 fooled | 0/24 fooled |
| llama3.1:8b | ranked **first** | **1/24** | 5/24 |
| llama3.2:3b | ranked second | **3/24** | 9/24 |
| llama3.2:3b | ranked **first** | **8/24** | 17/24 |

Full results: [`evals/injection_matrix.md`](evals/injection_matrix.md). Rendering kept every answer safe to display in all 192 attempts.

**What this shows, honestly:**
- **The defenses cut attack success by 2–5× wherever attacks land at all.** With the poison ranked second, the 8B model ignored everything even without defenses. That's why the first version of this test, which only used that setup, was inconclusive.
- **They don't stop "subtle poisoning":** a planted false fact written like normal content. No prompt can tell a lie from a fact. What helps is that the false claim is **cited**, for example "…also known as a PWNED-7731 attack [1]", so a reader can trace it to the poisoned source. Citations are the mitigation for this class of attack, not the prompt.
- **A weaker model is much easier to fool, with or without defenses.** That's why the default stays on the 8B model.
- **Rates vary run to run** (sampling temperature 0.2). Treat the numbers as rough proportions, not exact rates.

<details>
<summary><b>Self-audit before publishing</b> — a full security review of this repo found 4 issues, all fixed (expand)</summary>

| Found | Risk | Fix |
|---|---|---|
| The app listened on every network interface | Anyone on the same Wi-Fi could open the app and query your private documents | Binds to `127.0.0.1`; Docker publishes to `127.0.0.1` only. Verified: the LAN address is refused |
| Follow-up rewriting read earlier *answers* | Answers can quote a poisoned document, and the rewritten question lands in the prompt's trusted "Question" slot | The rewrite sees only the user's own questions; its output must be one line, ≤200 chars, no URLs. Unit-tested |
| No `.dockerignore` | Building the image baked private docs, the query log and `.env` into its layers | `.dockerignore` keeps them out; the container runs as a non-root user |
| Uncaught errors showed stack traces | Local file paths (including the OS username) visible in the browser | Error details hidden in the UI; still printed in the terminal |

Known and not applicable: `pip-audit` flags CVEs in ChromaDB 1.5.9, all in ChromaDB's standalone HTTP server. This app uses ChromaDB embedded in-process and never runs that server.

</details>

## How it works

```mermaid
flowchart LR
    Q[Question] --> S{Small talk?}
    S -- yes --> R0[Friendly reply]
    S -- no --> F{Follow-up?}
    F -- yes --> RW[Rewrite as a<br/>standalone question]
    F -- no --> HY
    RW --> HY[Hybrid retrieval<br/>MiniLM vectors + BM25, RRF]
    HY --> T{Closest passage<br/>within 0.75?}
    T -- no --> RF[Refusal]
    T -- yes --> W[Wrap passages as<br/>untrusted data] --> L[Ollama llama3.1:8b<br/>streamed]
    L --> G{Starts with<br/>a refusal?}
    G -- yes --> RF
    G -- no --> H[Escape HTML,<br/>add citation badges] --> UI[Streamlit UI]
```

| Layer | Choice | Runs |
|---|---|---|
| Embeddings | `all-MiniLM-L6-v2` (384-dim) on ONNX Runtime, no PyTorch | local CPU |
| Retrieval | hybrid: vectors + BM25 fused via RRF | local CPU |
| Vector DB | ChromaDB, persistent | local disk |
| LLM | Ollama `llama3.1:8b` (swappable via `.env`) | local GPU/CPU |
| UI | Streamlit, custom theme, self-hosted fonts | local |
| Tests | pytest + retrieval eval, GitHub Actions | CI |

## Quickstart

You need Python 3.11+ and [Ollama](https://ollama.com).

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull llama3.1:8b
python evals/run_eval.py --reingest   # builds the index from data/ and prints the eval report
streamlit run app.py
```

If Windows blocks `pip.exe` or `streamlit.exe` ("An Application Control policy has blocked this file"), run them through Python instead: `python -m pip install -r requirements.txt` and `python -m streamlit run app.py`.

**Mac / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.1:8b
python evals/run_eval.py --reingest
streamlit run app.py
```

To use your own documents, drop `.md`, `.txt` or `.pdf` files into `data/` and click **Rebuild knowledge base** in the sidebar. Settings (model, cutoff, passages per answer) live in `.env`; copy `.env.example` to start.

**Speed tips:**
- **Intel/AMD laptop with integrated graphics:** set `OLLAMA_IGPU_ENABLE=1`, otherwise Ollama ignores the iGPU.
- **Avoid reload pauses:** set `OLLAMA_KEEP_ALIVE=30m` so the model stays loaded between questions.
- **Apply them:** restart Ollama after setting either one.
- **Check it worked:** `ollama ps` should show `GPU` in the PROCESSOR column. Ollama 0.40.16 stopped detecting integrated GPUs through Vulkan; 0.40.13 works.

## Docker (one command, still fully local)

```bash
docker compose up --build
docker compose exec ollama ollama pull llama3.1:8b   # first run only
# open http://localhost:8501
```

The app runs in one container, Ollama in another; your corpus (`./data`), the
vector index, and the query log (`./cache`) are volume-mounted, so rebuilds
keep everything. No API keys, nothing leaves the machine except the model pull.

Inside Docker, Ollama can't use an integrated GPU, so answers run at CPU speed. For the fastest setup, run Ollama natively (see Quickstart).

## Observability

Every turn appends one JSONL record to `cache/query_log.jsonl` (gitignored — it stays on your machine): the query, retrieved sources with cosine distances, refusal/small-talk flags, and latency split into retrieval vs. total. Logged best-effort — a broken log file can never break a chat turn.

```python
from observability import summarize_line
summarize_line()   # "12 turns · refusal rate 8% · retrieval median 14.2ms · total median 2.4s"
```

## Under the hood: the retrieval step

![Retrieval trace: the passages found for each question, their distance, and the answer-or-refuse decision](docs/retrieval-trace.gif)

What happens before the LLM writes anything. For each question: the 3 passages retrieval found, their cosine distance (lower is closer; green is within the refusal cutoff), and the decision. The off-topic question is refused because even its closest passage is too far.

## Tests and evals

```bash
pytest -q                                  # 87 unit tests: chunking, cache, refusal, streaming, escaping, injection guards,
                                           #   hybrid retrieval (incl. a real in-memory ChromaDB), memory, observability
python evals/run_eval.py                   # retrieval hit-rate, fails below 80% (CI gate)
python evals/injection_eval.py             # live red-team (needs Ollama)
python evals/injection_eval.py --control   # same attacks against a naive undefended prompt
python evals/injection_eval.py --matrix    # full grid: models x defended/control x poison rank
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the unit tests and the retrieval eval on every push. The red-team needs a running LLM, so it runs locally; its latest reports are committed in [`evals/`](evals/).

To regenerate the README media: `pip install playwright`, then `python scripts/take_screenshots.py` (stills), `python scripts/record_demo_gif.py` (the demo recording, needs Ollama) and `python scripts/make_retrieval_trace.py` (the retrieval trace, no LLM needed). The first two drive the real app in a headless browser.

## Project layout

```
app.py                  # Streamlit entry point: wires UI + RAG together
rag.py                  # small talk -> follow-up rewrite -> retrieve -> refusal gate -> streamed, cited answer
retrieval.py            # hybrid retrieval: MiniLM vectors + BM25, fused with RRF
config.py               # settings from .env + lazy client singletons
observability.py        # per-turn JSONL query log + stats (refusal rate, latency)
warmup.py               # loads the embedding model + LLM in the background at launch
ingest/                 # loader (txt/md/pdf) -> chunker -> embedder (+ SQLite cache) -> ChromaDB
ui/                     # render.py (escape-first HTML), sidebar.py, knowledge_base.py, styles.css
evals/                  # retrieval eval + prompt-injection red-team, with reports
tests/                  # unit tests
scripts/                # screenshot, demo-recording and retrieval-trace generators
data/sample-corpus/     # AI-security sample documents
```

## Known limitations and roadmap

- **Subtle poisoning gets through the prompt layer.** A false fact written like normal content can be repeated — but it is cited to its source, so it's traceable (see Security model). No automated check can tell a well-written lie in the corpus from a fact; citations are the mitigation.
- [ ] Per-claim citation check: after the answer streams, verify each cited sentence against the passage it cites and flag unsupported claims. This catches hallucinated or injected claims; a lie planted in the corpus is still "supported" by its passage, which is why citations, not this check, are the answer to subtle poisoning.
- [ ] Cross-encoder re-ranking on top of hybrid retrieval (parked while the retrieval eval sits at 100% — there's nothing to measure an improvement against)

## License

[MIT](LICENSE). Bundled fonts (Fraunces, IBM Plex) are under the SIL Open Font License; see `static/fonts/`.
