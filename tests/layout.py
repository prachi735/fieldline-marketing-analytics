"""Check rendered local reports with Chromium. CI supplies the browser."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as engine:
    browser = engine.chromium.launch(executable_path=os.environ.get("CHROME_BIN"))
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    for width in (390, 1280):
        page.set_viewport_size({"width": width, "height": 900})
        for path in [ROOT / "index.html", ROOT / "01-dashboard/index.html", *ROOT.glob("*/report.html")]:
            page.goto(path.as_uri())
            if page.evaluate("document.documentElement.scrollWidth > innerWidth"):
                raise ValueError(f"Page overflow at {width}px: {path.name}")
            if path.parent.name == "01-dashboard" and width == 1280:
                card = page.locator("section").filter(has_text="Channel acquisition economics")
                if card.locator(".scroll").evaluate("(e) => e.scrollWidth > e.clientWidth"):
                    raise ValueError("Desktop channel table is clipped")
    if errors:
        raise RuntimeError(errors)
    browser.close()
