"""Rebuild from a clean temporary copy so existing example data stays intact."""
import csv
from contextlib import closing
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parent
def run(folder,script,*args):
    env=os.environ.copy()
    env.pop("PORTFOLIO_PG_DSN",None)
    subprocess.run([sys.executable,str(folder/script),*args],env=env,check=True)
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.paths.append(dict(attrs)["href"])
with tempfile.TemporaryDirectory() as tmp:
    dest=Path(tmp)/"rebuild"
    shutil.copytree(ROOT,dest,ignore=shutil.ignore_patterns("results","PowerBI",".git","__pycache__"))
    projects=sorted(p for p in dest.iterdir() if p.is_dir() and p.name[:2].isdigit())
    pipeline=projects[0]
    for args in [[],["--revision"],["--revision"]]:
        run(pipeline,"pipeline.py",*args)
    log=(pipeline/"results/execution.log").read_text()
    assert all(f"source_rows={n} watermark" in log for n in [240,5,0])
    with closing(sqlite3.connect(pipeline/"results/campaigns.sqlite")) as db:
        assert db.execute("SELECT COUNT(*),SUM(spend_cents) FROM campaign_day").fetchone()==(240,2961540)
    for folder in projects[1:]:
        run(folder,"audit.py" if folder==projects[-1] else "analyze.py")
    run(dest,"build_reports.py")
    run(dest,"build_powerbi.py")
    for f in dest.rglob("*.html"):
        links=Links()
        links.feed(f.read_text(encoding="utf-8"))
        assert all((f.parent/p).exists() for p in links.paths),str(f)
    for f in dest.rglob("*"):
        if f.suffix in {".json",".bim",".pbir",".pbism",".pbip"}:
            json.loads(f.read_text(encoding="utf-8"))
    for i in [1,2,3]:
        for expected in (ROOT/projects[i].name/"results").glob("*.csv"):
            assert expected.read_bytes()==(projects[i]/"results"/expected.name).read_bytes(),expected
    with (projects[-1]/"results/exceptions.csv").open() as f:
        findings=list(csv.DictReader(f))
    assert len(findings)==13 and len({r["rule"] for r in findings})==10
print("Verified all four projects, portfolio links and Power BI JSON files.")

