"""Record docs/demo.gif from the REAL app: a streamed, cited answer, the sources
panel, small talk, and a refusal. Same setup as take_screenshots.py (Ollama must
be running; Playwright drives the installed Edge, or Chromium on Mac/Linux).

Usage:
  python scripts/record_demo_gif.py [--browser chromium]
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from take_screenshots import URL, ask, start_app, wait_idle  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "demo.gif"
VIEWPORT = {"width": 1100, "height": 800}  # small window, saved at full size so text stays readable
FRAME_EVERY = 0.5          # seconds between captures while the answer streams
MAX_GAP = 0.8              # long waits (e.g. model thinking) are shortened to this
HOLD = 2.6                 # pause on key moments


class Recorder:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.frames: list[list] = []  # [image, seconds shown, duration fixed by a hold?]
        self.last = time.monotonic()

    def _follow_latest(self) -> None:
        # Keep the newest chat message in view (the chat input is fixed at the bottom).
        self.page.evaluate(
            """() => {
                const msgs = document.querySelectorAll('[data-testid="stChatMessage"]');
                if (msgs.length) msgs[msgs.length - 1].scrollIntoView({block: 'end'});
                const main = document.querySelector('[data-testid="stMain"]');
                if (main && msgs.length) main.scrollBy(0, 140);
            }"""
        )

    def snap(self, hold: float | None = None, follow: bool = True) -> None:
        if follow:
            self._follow_latest()
        now = time.monotonic()
        if self.frames and not self.frames[-1][2]:
            self.frames[-1][1] = min(now - self.last, MAX_GAP)  # show it as long as it was real, capped
        self.last = now
        img = Image.open(io.BytesIO(self.page.screenshot())).convert("RGB")
        self.frames.append([img, hold or FRAME_EVERY, hold is not None])

    def stream_until(self, text: str, timeout: float = 180) -> None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.snap()
            # exact=True: while the model thinks, a status line also mentions "3 sources".
            if self.page.get_by_text(text, exact=True).count():
                return
            time.sleep(FRAME_EVERY)
        raise TimeoutError(f"never saw {text!r}")

    def save(self, path: Path) -> None:
        # Shared palette: dark UI quantizes cleanly and keeps the file small.
        frames = [img.quantize(colors=96, method=Image.Quantize.MEDIANCUT) for img, _, _ in self.frames]
        durations = [max(80, int(min(d, 10) * 1000)) for _, d, _ in self.frames]
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", choices=["msedge", "chromium"], default="msedge")
    args = parser.parse_args()

    app = start_app()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge" if args.browser == "msedge" else None)
            page = browser.new_page(viewport=VIEWPORT)
            page.goto(URL)
            page.get_by_text("Try asking").wait_for(timeout=60_000)
            wait_idle(page)
            rec = Recorder(page)
            rec.snap(hold=HOLD, follow=False)

            page.get_by_role("button", name="What is indirect prompt injection?").click()
            rec.stream_until("3 sources")
            wait_idle(page)
            rec.snap(hold=HOLD)

            page.get_by_text("3 sources", exact=True).click()
            page.wait_for_timeout(600)
            page.get_by_text("3 sources", exact=True).evaluate("el => el.scrollIntoView({block: 'start'})")
            rec.snap(hold=HOLD + 0.8, follow=False)

            ask(page, "thanks!")
            wait_idle(page)
            rec.snap(hold=1.8)

            ask(page, "What's the capital of France?")
            rec.stream_until("Outside the knowledge base")
            wait_idle(page)
            page.get_by_text("Outside the knowledge base").evaluate("el => el.scrollIntoView({block: 'center'})")
            page.wait_for_timeout(300)
            rec.snap(hold=HOLD + 1.0, follow=False)
            browser.close()
        rec.save(OUT)
        print(f"saved {OUT} ({len(rec.frames)} frames, {OUT.stat().st_size / 1e6:.1f} MB)")
    finally:
        app.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
