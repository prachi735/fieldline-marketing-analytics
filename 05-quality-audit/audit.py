"""Reconcile a synthetic ad-platform export to a deliberately imperfect extract."""
import csv
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT/"results"


def generate_extract():
    fields = ["day", "account", "campaign", "channel", "currency",
              "minor_units", "clicks", "reported_cpc_usd", "loaded_on"]
    source = []
    for day in range(14):
        dt = date(2025, 3, 1)+timedelta(days=day)
        for account in range(3):
            for ch, channel in enumerate(["Search", "LinkedIn", "Display", "Review"]):
                native = 9200+280*account+425*ch+83*day
                clicks = 20+day*2+ch
                fx = [1, 1.08, 1.27][account]
                source.append([dt.isoformat(), f"A{account+1}", f"P{ch+1}", channel, ["USD", "EUR", "GBP"]
                              [account], native, clicks, round(native*fx/100/clicks, 2), (dt+timedelta(days=1)).isoformat()])
    extract = [r.copy() for r in source]
    extract.append(source[3].copy())
    extract[11][3] = ""
    extract[22][4] = "EURO"
    extract[37][3] = "Paid_Srch"
    extract[46][5] += 2300
    extract[47][7] += 1.25
    extract[64][8] = "2025-03-15"
    extract[75][6] += 4
    del extract[80]
    extract.append(["2025-03-14", "A9", "P1", "Search", "USD", 2250, 15, 1.5, "2025-03-15"])
    return fields, source, extract


def main():
    OUT.mkdir(exist_ok=True)
    fields, source, extract = generate_extract()

    def save(name, header, rows):
        with (OUT/(name+".csv")).open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    db = sqlite3.connect(":memory:")
    schema = "(day TEXT,account TEXT,campaign TEXT,channel TEXT,currency TEXT,minor_units INTEGER,clicks INTEGER,reported_cpc_usd REAL,loaded_on TEXT)"
    for name, data in [("source", source), ("extract", extract)]:
        save(name, fields, data)
        db.execute("CREATE TABLE "+name+schema)
        db.executemany("INSERT INTO "+name+" VALUES(?,?,?,?,?,?,?,?,?)", data)
    db.executescript((ROOT/"checks.sql").read_text())
    db.row_factory = sqlite3.Row
    for name, query in [
        ("exceptions", "SELECT * FROM exceptions ORDER BY severity,rule,day,account,campaign"),
        ("scorecard", "SELECT r.rule,r.owner,r.action,COUNT(e.rule) AS exceptions FROM rules r LEFT JOIN exceptions e USING(rule) GROUP BY r.rule ORDER BY exceptions DESC,r.rule"),
        ("reconciliation", "SELECT * FROM daily ORDER BY day")
    ]:
        cur = db.execute(query)
        save(name, [x[0] for x in cur.description], cur)
    diff = db.execute("SELECT ROUND(SUM(variance_usd),2) FROM daily").fetchone()[0]
    print("Exception findings:", db.execute("SELECT COUNT(*) FROM exceptions").fetchone()
          [0], "convertible spend variance USD:", diff)


if __name__ == "__main__":
    main()
