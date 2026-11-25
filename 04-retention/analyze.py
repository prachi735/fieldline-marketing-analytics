"""Customer cohorts, fixed RFM bands and forward contribution by segment."""
import csv
import random
import sqlite3
from calendar import monthrange
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT/"results"


def generate_orders():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE orders(order_id INTEGER PRIMARY KEY, customer_id INTEGER, month_no INTEGER, order_date TEXT, net_cents INTEGER)")
    rng = random.Random(471)
    orders = []
    for customer in range(1, 1501):
        first = rng.choices(range(12), [7, 8, 7, 8, 8, 8, 8, 8, 9, 9, 10, 10])[0]
        repeat = rng.uniform(.10, .54)
        for m in range(first, 12):
            if m == first or rng.random() < repeat*(.93**(m-first)):
                day = rng.randint(1, monthrange(2025, m+1)[1])
                orders.append((len(orders)+1, customer, m,
                              f"2025-{m+1:02}-{day:02}", rng.randint(2500, 19500)))
    db.executemany("INSERT INTO orders VALUES(?,?,?,?,?)", orders)
    db.execute("CREATE TEMP VIEW customers AS "+(ROOT/"customers.sql").read_text())
    return db, orders


def main():
    OUT.mkdir(exist_ok=True)
    db, orders = generate_orders()

    def save(name, headers, rows):
        with (OUT/(name+".csv")).open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
    save("orders", ["order_id", "customer_id", "month_no", "order_date", "net_cents"], orders)
    cohorts = []
    for c in range(12):
        size = db.execute("SELECT COUNT(*) FROM customers WHERE cohort=?", (c,)).fetchone()[0]
        for age in range(12-c):
            active = db.execute(
                "SELECT COUNT(DISTINCT customer_id) FROM orders JOIN customers USING(customer_id) WHERE cohort=? AND month_no=?", (c, c+age)).fetchone()[0]
            cohorts.append((c+1, age, size, active, active/size))
    save("cohorts", ["cohort_month", "age", "cohort_size", "active", "retention"], cohorts)

    def band(value, third, second):
        return 3 if value >= third else 2 if value >= second else 1
    segments = {}
    historical_value = {}
    detail = []
    for row in db.execute("SELECT * FROM customers"):
        r = 3 if row["recency_days"] <= 30 else 2 if row["recency_days"] <= 90 else 1
        f = band(row["frequency"], 4, 2)
        m = band(row["net_sales"], 450, 180)
        seg = "Champions" if r == 3 and f == 3 and m >= 2 else "At risk" if r == 1 and f >= 2 else "Recent first-time" if r == 3 and f == 1 else "Other repeat" if f >= 2 else "Other first-time"
        detail.append((*row, r, f, m, seg))
        segments[row["customer_id"]] = seg
        historical_value[row["customer_id"]] = row["net_sales"]*.55
    save("customers", ["customer_id", "cohort", "last_active", "frequency",
         "net_sales", "recency_days", "R", "F", "M", "segment"], detail)
    # For each three-month horizon, freeze the eligible base at its start.
    # Estimate from the preceding quarter's spend by this same customer base.

    def horizon(start):
        rows = db.execute("""SELECT customer_id,
            sum(CASE WHEN month_no>=?-3 AND month_no<? THEN net_cents ELSE 0 END)/100.0 AS recent,
            sum(CASE WHEN month_no>=? AND month_no<?+3 THEN net_cents ELSE 0 END)/100.0 AS actual
            FROM orders GROUP BY customer_id HAVING min(month_no)<?""", (start, start, start, start, start))
        return [(r[0], r[1]*.55, r[2]*.55) for r in rows]
    holdout = horizon(9)
    # Calibrate aggregate carryover on Q2 spending and Q3 outcomes, then freeze it for Q4.
    training = horizon(6)
    carryover = sum(r[2] for r in training)/sum(r[1] for r in training)
    baseline = sum(r[1] for r in holdout)
    pred = baseline*carryover
    observed = sum(r[2] for r in holdout)
    save("backtest", ["eligible_customers", "carryover", "baseline_contribution", "predicted_contribution", "actual_contribution", "aggregate_error_pct", "customer_mae_usd"], [
         (len(holdout), carryover, baseline, pred, observed, (pred-observed)/observed, sum(abs(r[1]*carryover-r[2]) for r in holdout)/len(holdout))])
    summary = {}
    for customer, forward, _ in horizon(12):
        seg = segments[customer]
        bucket = summary.setdefault(seg, [0, 0, 0])
        bucket[0] += 1
        bucket[1] += historical_value[customer]
        bucket[2] += forward*carryover
    save("segment_value", ["segment", "customers", "observed_contribution_usd", "projected_90d_contribution_usd", "ltv_through_mar_per_customer"], [
         (s, n, hist, next_q, (hist+next_q)/n) for s, (n, hist, next_q) in sorted(summary.items())])
    if len(detail) != 1500 or sum(v[0] for v in summary.values()) != len(detail):
        raise ValueError("Segment counts disagree with customer population")
    if any(rate < 0 or rate > 1 or (age == 0 and rate != 1) for _, age, _, _, rate in cohorts):
        raise ValueError("Invalid cohort retention")
    print("Customers:", len(detail), "orders:", len(orders), "observed cohort cells:", len(cohorts))


if __name__ == "__main__":
    main()
