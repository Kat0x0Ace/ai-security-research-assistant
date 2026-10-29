"""Retrieval eval runner.

Measures retrieval hit-rate: for each case in evals/eval_set.yaml, the
expected source must appear in the top-k retrieved sources. No LLM needed —
this tests the retrieval half of the pipeline, which is the part CI can gate.

Usage:
  python evals/run_eval.py            # ingest sample corpus if empty, run eval
  python evals/run_eval.py --reingest # force re-ingestion first

Output: a Markdown report printed to stdout (CI-logged) and written to
evals/eval_report.md. Exit code 1 if hit-rate < threshold.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the project root importable when run as a script (python evals/run_eval.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from config import DATA_DIR, LLM_TOP_K, get_collection

EVAL_SET = Path(__file__).parent / "eval_set.yaml"
REPORT = Path(__file__).parent / "eval_report.md"
DEFAULT_THRESHOLD = 0.80


def ensure_corpus_ingested(force: bool = False) -> None:
    collection = get_collection()
    if force or collection.count() == 0:
        from ingest.pipeline import ingest_data_dir

        summary = ingest_data_dir(DATA_DIR)
        print(f"[eval] ingested: {summary}")


def run_eval() -> dict:
    """Run the eval set. Returns a summary dict with hit-rate."""
    from rag import retrieve

    spec = yaml.safe_load(EVAL_SET.read_text(encoding="utf-8"))
    top_k = spec.get("top_k", 3)
    cases = spec["cases"]

    results = []
    for case in cases:
        hits = retrieve(case["question"], top_k=top_k)
        sources = {h.source for h in hits}
        hit = any(case["expect_source"] in src for src in sources)
        results.append(
            {
                "question": case["question"],
                "expected": case["expect_source"],
                "retrieved": sorted(sources),
                "hit": hit,
            }
        )

    hit_rate = sum(r["hit"] for r in results) / len(results) if results else 0.0
    return {
        "name": spec.get("name", "eval"),
        "top_k": top_k,
        "cases": results,
        "hit_rate": hit_rate,
        "num_cases": len(results),
    }


def render_report(summary: dict) -> str:
    lines = [
        f"# Retrieval eval report — {summary['name']}",
        "",
        f"- Cases: {summary['num_cases']} (top_k={summary['top_k']})",
        f"- Hit rate: **{summary['hit_rate']:.1%}**",
        "",
        "| # | Question | Expected source | Hit |",
        "|---|----------|-----------------|-----|",
    ]
    for i, r in enumerate(summary["cases"], start=1):
        lines.append(
            f"| {i} | {r['question']} | {r['expected']} | {'✅' if r['hit'] else '❌'} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run retrieval eval suite")
    parser.add_argument("--reingest", action="store_true", help="re-ingest data/ first")
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD, help="min hit-rate to pass"
    )
    args = parser.parse_args()

    ensure_corpus_ingested(force=args.reingest)
    summary = run_eval()
    report = render_report(summary)
    print(report)
    REPORT.write_text(report, encoding="utf-8")
    print(f"\n[eval] hit-rate {summary['hit_rate']:.1%} (threshold {args.threshold:.0%})")
    return 0 if summary["hit_rate"] >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
