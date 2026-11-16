"""Measure the per-claim citation check (verify.py) against the live local LLM.

Two measurements over the retrieval eval questions (evals/eval_set.yaml):

  A. False flags — answer each question, run the check on the grounded answer.
     A good checker flags (almost) nothing here: these answers come straight
     from the sources.
  B. Sensitivity — append one fabricated cited sentence to the same answer and
     run the check again. A good checker flags exactly that sentence.

Writes evals/verify_report.md. Needs Ollama running.

Usage:
  python evals/verify_eval.py [--limit N]
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag import answer  # noqa: E402
from verify import UNSUPPORTED, verify_answer  # noqa: E402

EVAL_SET = Path(__file__).parent / "eval_set.yaml"
REPORT = Path(__file__).parent / "verify_report.md"

# Plausible-sounding domain lies that appear nowhere in the sample corpus.
FABRICATIONS = [
    "This technique was first standardized by ISO in 1987",
    "Researchers at CERN patented the main defense against this in 2003",
    "This attack only affects models smaller than one billion parameters",
    "OWASP retired this risk from its Top 10 in 2019",
    "Exploiting this requires physical access to the GPU",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only run the first N questions")
    args = parser.parse_args()

    cases = yaml.safe_load(EVAL_SET.read_text(encoding="utf-8"))["cases"][: args.limit]
    rows, verify_times = [], []
    refused = uncited = clean_flags = corrupted_caught = corrupted_run = 0

    for i, case in enumerate(cases, start=1):
        question = case["question"]
        result = answer(question)
        if result.refused:
            refused += 1
            rows.append((question, "—", "refused", "—"))
            continue

        t0 = time.perf_counter()
        clean = verify_answer(result.answer, result.sources)
        verify_times.append(time.perf_counter() - t0)
        if clean.status == "uncited":
            uncited += 1
            rows.append((question, "0", "uncited", "—"))
            continue
        clean_flagged = len(clean.flagged)
        clean_flags += clean_flagged

        lie = FABRICATIONS[i % len(FABRICATIONS)]
        corrupted = f"{result.answer}\n\n{lie} [1]."
        t0 = time.perf_counter()
        poisoned = verify_answer(corrupted, result.sources)
        verify_times.append(time.perf_counter() - t0)
        if poisoned.status == "unverified":
            outcome = "unverified"
        else:
            caught = any(
                c.verdict == UNSUPPORTED and lie.split()[-3] in c.sentence for c in poisoned.claims
            )
            corrupted_run += 1
            corrupted_caught += caught
            outcome = "caught" if caught else "MISSED"

        rows.append((question, str(len(clean.claims)), f"{clean_flagged} flagged", outcome))
        print(f"[{i:2}/{len(cases)}] claims={len(clean.claims)} clean={clean.status} lie={outcome}  {question[:60]}")

    median_s = statistics.median(verify_times) if verify_times else 0.0
    answered = len(cases) - refused

    lines = [
        "# Citation-check eval",
        "",
        f"{len(cases)} eval questions · grounded answers from the live model, then the same answer with one fabricated cited sentence appended.",
        "",
        f"- **False flags on grounded answers:** {clean_flags} across {answered} answers",
        f"- **Fabricated cited claims caught:** {corrupted_caught}/{corrupted_run} (runs where the verifier's reply didn't parse are excluded and listed as *unverified*)",
        f"- **Answers with no citations (check can't help):** {uncited}",
        f"- **Refusals (never reach the check):** {refused}",
        f"- **Median check latency:** {median_s:.1f}s per answer (one batched LLM call)",
        "",
        "| Question | Claims | Clean answer | Fabricated claim |",
        "|---|---|---|---|",
        *(f"| {q} | {c} | {a} | {b} |" for q, c, a, b in rows),
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {REPORT}")
    print(f"false flags {clean_flags}/{answered} · lies caught {corrupted_caught}/{corrupted_run} · median {median_s:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
