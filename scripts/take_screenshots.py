"""Regenerate the README screenshots by driving the real app in a headless browser.

Starts the Streamlit app on a spare port, asks it real questions (so Ollama must
be running), and saves PNGs to docs/screenshots/.

Dev-only dependency (not in requirements.txt):
  pip install playwright
  # Uses the installed Microsoft Edge (Windows) via channel="msedge".
  # On Mac/Linux: `playwright install chromium` and run with --browser chromium.

Usage:
  python scripts/take_screenshots.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
PORT = 8599
URL = f"http://127.0.0.1:{PORT}"


def start_app() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true", "--server.port", str(PORT)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{URL}/_stcore/health", timeout=1)
            return proc
        except OSError:
            time.sleep(1)
    proc.terminate()
    raise RuntimeError("Streamlit did not start")


def ask(page: Page, question: str) -> None:
    box = page.get_by_placeholder("Ask about AI security…")
    box.fill(question)
    box.press("Enter")


def wait_idle(page: Page) -> None:
    """Wait until Streamlit has finished the current run."""
    page.wait_for_timeout(500)
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=180_000)
    page.wait_for_timeout(800)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=["msedge", "chromium"], default="msedge")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    app = start_app()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge" if args.browser == "msedge" else None)
            page = browser.new_page(viewport={"width": 1440, "height": 960}, device_scale_factor=2)
            page.goto(URL)
            page.get_by_text("Try asking").wait_for(timeout=60_000)
            wait_idle(page)
            page.screenshot(path=OUT / "empty-state.png")

            page.get_by_role("button", name="What is indirect prompt injection?").click()
            page.get_by_text("3 sources").wait_for(timeout=180_000)
            wait_idle(page)
            page.get_by_text("3 sources").click()
            page.wait_for_timeout(600)
            page.get_by_text("3 sources").scroll_into_view_if_needed()
            page.screenshot(path=OUT / "cited-answer.png")

            ask(page, "thanks!")
            wait_idle(page)
            ask(page, "What's the capital of France?")
            page.get_by_text("Outside the knowledge base").wait_for(timeout=180_000)
            wait_idle(page)
            # scroll_into_view_if_needed() counts the callout as "visible" even when the
            # fixed chat input covers it, so centre it explicitly.
            page.get_by_text("Outside the knowledge base").evaluate("el => el.scrollIntoView({block: 'center'})")
            page.wait_for_timeout(400)
            page.screenshot(path=OUT / "refusal.png")
            browser.close()
    finally:
        app.terminate()
        app.wait(timeout=20)
    for f in sorted(OUT.glob("*.png")):
        print(f"saved {f.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
