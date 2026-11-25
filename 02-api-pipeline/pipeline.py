"""Run a paginated HTTP fixture and load changed campaign-day records atomically."""
import argparse
import csv
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"
CHANNELS = ["Paid Search", "LinkedIn Ads", "Display", "Review Sites"]
FIELDS = ["client", "campaign", "day", "channel", "spend_cents", "clicks", "updated_at"]

def records(revision):
    for day in range(12):
        for client in range(5):
            for channel, name in enumerate(CHANNELS):
                dt = (date(2025, 1, 1) + timedelta(days=day)).isoformat()
                corrected = revision and day == 2 and channel == 1
                yield dict(zip(FIELDS, [f"C{client+1}", f"K{channel+1}", dt, name,
                           8500 + client*1241 + channel*502 + day*107 + (780 if corrected else 0),
                           19 + day + client*4 + channel,
                           "2025-01-14T12:00:00Z" if corrected else dt+"T12:00:00Z"]))

class MockAPI(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.split("?")[0] != "/campaigns":
            self.send_error(404)
            return
        if self.server.throttle:
            self.server.throttle = False
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.end_headers()
            return
        query = parse_qs(urlsplit(self.path).query)
        since = query.get("since", [""])[0]
        offset = int(query.get("offset", ["0"])[0])
        eligible = [r for r in records(self.server.revision) if r["updated_at"] > since]
        page = eligible[offset:offset+37]
        following = offset + len(page)
        payload = json.dumps({"data": page, "next": following if following < len(eligible) else None}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(url, timeout=10) as response:
                return json.load(response)
        except HTTPError as err:
            if attempt == 2 or err.code not in (429, 500, 502, 503, 504):
                raise
            delay = int(err.headers.get("Retry-After", 2**attempt))
            logging.info("HTTP %s | retry %s", err.code, attempt+1)
            time.sleep(delay)

def ingest(db, api, marker):
    db.execute("CREATE TABLE IF NOT EXISTS campaign_day (client TEXT, campaign TEXT, day TEXT, channel TEXT, spend_cents INTEGER CHECK(spend_cents>=0), clicks INTEGER CHECK(clicks>=0), updated_at TEXT, PRIMARY KEY(client,campaign,day))")
    db.execute("CREATE TABLE IF NOT EXISTS state (stream TEXT PRIMARY KEY, watermark TEXT)")
    previous = db.execute("SELECT watermark FROM state WHERE stream='ads'").fetchone()
    watermark = previous[0] if previous else ""
    maximum = watermark
    offset = count = pages = 0
    while offset is not None:
        payload = fetch(api+"?"+urlencode({"since": watermark, "offset": offset}))
        for row in payload["data"]:
            if any(row.get(k) is None for k in FIELDS) or row["channel"] not in CHANNELS:
                raise ValueError("Incomplete or invalid source row")
            args = tuple(row[k] for k in FIELDS)
            db.execute("INSERT INTO campaign_day VALUES ("+",".join([marker]*len(args))+") ON CONFLICT(client,campaign,day) DO UPDATE SET spend_cents=excluded.spend_cents,clicks=excluded.clicks,channel=excluded.channel,updated_at=excluded.updated_at WHERE excluded.updated_at>=campaign_day.updated_at", args)
            maximum = max(maximum, row["updated_at"])
            count += 1
        pages += 1
        offset = payload["next"]
    db.execute("INSERT INTO state VALUES ('ads',"+marker+") ON CONFLICT(stream) DO UPDATE SET watermark=excluded.watermark", (maximum,))
    db.commit()
    logging.info("pages=%s source_rows=%s watermark=%s", pages, count, maximum)
    return count

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", action="store_true", help="Source includes five late corrections")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.FileHandler(OUT/"execution.log"),logging.StreamHandler()])
    dsn = os.getenv("PORTFOLIO_PG_DSN")
    if dsn:
        import psycopg
        db = psycopg.connect(dsn)
    else:
        db = sqlite3.connect(OUT/"campaigns.sqlite")
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockAPI)
    server.revision, server.throttle = args.revision, True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        ingest(db, f"http://127.0.0.1:{server.server_port}/campaigns", "%s" if dsn else "?")
        for name, query in [("campaign_day","SELECT * FROM campaign_day ORDER BY day,client,campaign"),("channel_summary",(ROOT/"channel_summary.sql").read_text())]:
            cur = db.execute(query)
            with (OUT/(name+".csv")).open("w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([col[0] for col in cur.description])
                writer.writerows(cur)
        (OUT/"sample-response.json").write_text(json.dumps(list(records(args.revision))[:3],indent=2))
    finally:
        db.close()
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    main()

