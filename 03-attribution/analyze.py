"""Generate deterministic closed-cohort journeys and compare attribution policies."""
import csv
import random
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT/"results"


def generate_journeys():
    rng = random.Random(318)
    db = sqlite3.connect(":memory:")
    db.executescript("""CREATE TABLE touches(lead_id INTEGER,touch_no INTEGER,channel TEXT,PRIMARY KEY(lead_id,touch_no));
    CREATE TABLE leads(lead_id INTEGER PRIMARY KEY,qualified INTEGER,opportunity INTEGER,won INTEGER,pipeline REAL,revenue REAL);
    CREATE TABLE spend(channel TEXT PRIMARY KEY,spend_usd REAL);
    CREATE TABLE models(model TEXT PRIMARY KEY);""")
    channels = ["Paid Search", "LinkedIn Ads", "Display", "Review Sites"]
    db.executemany("INSERT INTO spend VALUES(?,?)", zip(channels, [216000, 192000, 120000, 72000]))
    db.executemany("INSERT INTO models VALUES(?)", [(m,)
                   for m in ["First touch", "Last touch", "Linear"]])
    for lead in range(1, 3201):
        first = rng.choices(channels, [32, 35, 24, 9])[0]
        path = [first]
        for step in range(rng.choices([0, 1, 2, 3], [18, 39, 31, 12])[0]):
            path.append(rng.choices(channels, [42, 13, 10, 35])[0])
        qualified = int(rng.random() < [.51, .42, .22, .58][channels.index(first)])
        opportunity = int(qualified and rng.random() < .36)
        won = int(opportunity and rng.random() < .32)
        amount = rng.randrange(9, 42)*1000 if opportunity else 0
        db.execute("INSERT INTO leads VALUES(?,?,?,?,?,?)",
                   (lead, qualified, opportunity, won, amount, amount*won))
        db.executemany("INSERT INTO touches VALUES(?,?,?)", [
                       (lead, i+1, ch) for i, ch in enumerate(path)])
    return db


def main():
    OUT.mkdir(exist_ok=True)
    db = generate_journeys()

    def export(name, query):
        cursor = db.execute(query)
        with (OUT/(name+".csv")).open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([x[0] for x in cursor.description])
            writer.writerows(cursor)
    for table in ["leads", "touches", "spend"]:
        export(table, "SELECT * FROM "+table)
    db.execute("CREATE TEMP TABLE comparison AS "+(ROOT/"attribution.sql").read_text())
    export("comparison", "SELECT * FROM comparison")
    # Hold the transfer and spend-response assumption fixed across credit models.
    export("budget_scenarios", """WITH yields AS (
        SELECT model,
               MAX(CASE WHEN channel='Display' THEN revenue_usd/spend_usd END) AS display_roas,
               MAX(CASE WHEN channel='Review Sites' THEN revenue_usd/spend_usd END) AS review_sites_roas
        FROM comparison GROUP BY model
    )
    SELECT model, 10000 AS transfer_usd,
           ROUND(display_roas, 4) AS display_roas, ROUND(review_sites_roas, 4) AS review_sites_roas,
           ROUND(10000 * (review_sites_roas - display_roas), 2) AS revenue_change_usd,
           ROUND(0.72 * 10000 * (review_sites_roas - display_roas), 2) AS gross_profit_change_usd
    FROM yields ORDER BY CASE model WHEN 'First touch' THEN 1 WHEN 'Last touch' THEN 2 ELSE 3 END""")
    reference = db.execute(
        "SELECT count(*),sum(qualified),sum(opportunity),sum(won),sum(pipeline),sum(revenue) FROM leads").fetchone()
    for row in db.execute("SELECT sum(leads),sum(qualified),sum(opportunities),sum(wins),sum(pipeline_usd),sum(revenue_usd) FROM comparison GROUP BY model"):
        if any(abs(a-b) >= .001 for a, b in zip(row, reference)):
            raise ValueError("Attribution model failed to reconcile")
    print("Every model reconciles to cohort totals:", reference)


if __name__ == "__main__":
    main()
