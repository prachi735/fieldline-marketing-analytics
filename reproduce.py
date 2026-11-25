"""Build in a clean temporary directory and check the five portfolio projects."""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
ANALYSES = {
    "03-attribution": "analyze.py",
    "04-retention": "analyze.py",
    "05-quality-audit": "audit.py",
}


def run(script, *args):
    env = os.environ.copy()
    env.pop("PORTFOLIO_PG_DSN", None)
    subprocess.run([sys.executable, str(script), *args], env=env, check=True)


class LocalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            url = urlsplit(dict(attrs).get("href", ""))
            if not url.netloc and not url.scheme and url.path:
                self.paths.append(url.path)


def check_pages(root):
    for page in root.rglob("*.html"):
        links = LocalLinks()
        links.feed(page.read_text(encoding="utf-8"))
        for path in links.paths:
            if not (page.parent / path).is_file():
                raise ValueError(f"Broken link in {page.name}: {path}")
    for file in root.rglob("*"):
        if file.suffix in {".json", ".bim", ".pbir", ".pbism", ".pbip"}:
            json.loads(file.read_text(encoding="utf-8"))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "portfolio"
        shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(
            "results", "PowerBI", ".git", ".codex", "__pycache__", ".pytest_cache"
        ))
        pipeline = dest / "02-api-pipeline" / "pipeline.py"
        for args in [(), ("--revision",), ("--revision",)]:
            run(pipeline, *args)
        log = (pipeline.parent / "results" / "execution.log").read_text()
        counts = [line.split("source_rows=")[1].split()[0]
                  for line in log.splitlines() if "source_rows=" in line]
        if counts != ["240", "5", "0"]:
            raise ValueError(f"Unexpected initial, correction and replay counts: {counts}")
        for slug, script in ANALYSES.items():
            run(dest / slug / script)
            for expected in (ROOT / slug / "results").glob("*.csv"):
                actual = dest / slug / "results" / expected.name
                with actual.open(newline="") as a, expected.open(newline="") as e:
                    if list(csv.reader(a)) != list(csv.reader(e)):
                        raise ValueError(f"Result changed: {slug}/{actual.name}")
        run(dest / "build_reports.py")
        run(dest / "build_powerbi.py")
        check_pages(dest)
        run_node = shutil.which("node")
        if run_node is None:
            raise RuntimeError("Install Node.js to check the interactive dashboard.")
        subprocess.run([run_node, str(dest / "tests" / "dashboard.cjs")], cwd=dest, check=True)
    print("Verified five portfolio projects and their report links.")


if __name__ == "__main__":
    main()
