"""Regression checks. Run with pytest or Python's unittest discovery."""
import csv
import importlib.util
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pipeline", ROOT / "02-api-pipeline/pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class PortfolioTests(unittest.TestCase):
    def test_correction_and_stale_replay(self):
        row = next(pipeline.records(False))
        newer = dict(row, spend_cents=12345, updated_at="2025-02-01T00:00:00Z")
        with closing(sqlite3.connect(":memory:")) as db:
            for snapshot in (row, newer, row):
                with patch.object(pipeline, "fetch", return_value={"data": [snapshot], "next": None}):
                    pipeline.ingest(db, "http://fixture", "?")
            self.assertEqual(db.execute(
                "SELECT spend_cents FROM campaign_day").fetchall(), [(12345,)])
            self.assertEqual(db.execute("SELECT watermark FROM state").fetchone()
                             [0], newer["updated_at"])

    def test_transient_network_failure_has_bounded_retries(self):
        with patch.object(pipeline, "urlopen", side_effect=URLError("offline")) as request:
            with patch.object(pipeline.time, "sleep") as sleep:
                with self.assertRaises(URLError):
                    pipeline.fetch("http://fixture")
            self.assertEqual(request.call_count, 3)
            self.assertEqual([call.args for call in sleep.call_args_list], [(1,), (2,)])

    def test_currency_only_mismatch_and_reconciliation(self):
        folder = ROOT / "05-quality-audit"
        columns = """day TEXT, account TEXT, campaign TEXT, channel TEXT, currency TEXT,
                     minor_units INTEGER, clicks INTEGER, reported_cpc_usd REAL, loaded_on TEXT"""
        with closing(sqlite3.connect(":memory:")) as db:
            for name in ("source", "extract"):
                db.execute(f"CREATE TABLE {name} ({columns})")
                with (folder / "results" / f"{name}.csv").open() as f:
                    rows = csv.reader(f)
                    next(rows)
                    db.executemany(f"INSERT INTO {name} VALUES(?,?,?,?,?,?,?,?,?)", rows)
            db.executescript((folder / "checks.sql").read_text())
            evidence = db.execute("""SELECT evidence FROM exceptions WHERE rule='Spend mismatch'
                AND day='2025-03-02' AND account='A3' AND campaign='P3'""").fetchone()[0]
            self.assertIn("EURO 10693", evidence)
            self.assertIn("GBP 10693", evidence)
            self.assertEqual(db.execute(
                "SELECT COUNT(*), COUNT(DISTINCT rule) FROM exceptions").fetchone(), (13, 10))
            self.assertEqual(db.execute(
                "SELECT ROUND(SUM(variance_usd),2), SUM(unpriced_rows) FROM daily").fetchone(), (-109.62, 1))
