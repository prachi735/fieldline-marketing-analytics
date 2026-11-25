"""Build the offline HTML portfolio from the CSVs produced by the four projects."""
import csv
import json
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent
STYLE = """
*{box-sizing:border-box}body{margin:0;background:#f7f6f1;color:#162c2a;font:16px/1.55 'DM Sans',Arial,sans-serif}main{max-width:1160px;margin:auto;padding:30px clamp(16px,4vw,58px) 60px}header{background:#103c38;color:white;padding:32px max(calc((100vw - 1050px)/2),5vw) 44px}header span{color:#bae8c8;font-weight:700;letter-spacing:.08em;font-size:13px}h1{font:500 clamp(30px,5vw,54px)/1.03 Georgia,serif;margin:18px 0}h2{font:500 28px Georgia,serif;margin:0 0 16px}header p{max-width:780px;color:#e2eee7}a{color:#16635b}article,section,details{background:white;border:1px solid #d8ded8;border-radius:10px;padding:22px;margin-bottom:16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}.grid strong{display:block;font:500 clamp(22px,3vw,34px) Georgia,serif}.grid small,.note{color:#4f6563}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}th,td{text-align:right;white-space:nowrap;border-bottom:1px solid #dce5df;padding:8px}th:first-child,td:first-child{text-align:left}label{display:inline-flex;align-items:center;gap:10px}select{font:inherit;padding:6px;border-radius:5px}.bar{display:grid;grid-template-columns:110px 1fr 90px;gap:12px;align-items:center;margin:8px 0}.track{background:#e3efeb}.fill{height:14px;background:#38826e}summary{cursor:pointer;font-weight:bold}details a{margin-right:15px}
"""


def cards(pairs):
    return '<div class="grid">'+''.join(f'<article><strong>{v}</strong><small>{k}</small></article>' for k, v in pairs)+'</div>'


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>'+''.join(f'<th>{h}</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{x}</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def section(title, body):
    return f'<section><h2>{title}</h2>{body}</section>'


def page(title, kicker, lede, body):
    return f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>{STYLE}</style><header><span>{kicker}</span><h1>{title}</h1><p>{lede}</p></header><main>{body}</main></html>'


def read(folder, name):
    with (folder/"results"/(name+".csv")).open() as f:
        return list(csv.DictReader(f))


def usd(x):
    value = float(x)
    return ("−" if value < 0 else "") + f"${abs(value):,.0f}"


def pct(x):
    return "{:.1%}".format(float(x))


def pipeline_report(folder):
    data = read(folder, "channel_summary")
    body = cards([("Campaign-day keys", "240"),
                 ("Late corrections", "5"), ("Rows read on replay", "0")])
    body += section("What happened on refresh", table(["Run", "Pages", "Source rows", "Result"], [["Initial load", 7, 240, "240 unique keys"], [
                    "Corrected snapshot", 1, 5, "+$39.00 across existing keys"], ["Replay", 1, 0, "No additional spend"]]))
    body += section("Channel totals after correction", table(["Channel", "Rows", "Spend", "Clicks", "Cost per click"], [
                    [r["channel"], r["campaign_days"], usd(r["spend_usd"]), r["clicks"], "$"+r["cost_per_click"]] for r in data]))
    body += section("Pipeline walkthrough",
                    '<video controls preload="metadata" style="width:100%" src="pipeline-walkthrough.webm"></video>')
    decision = "Schedule the incremental load. Monitor watermark age and compare daily spend with the platform ledger after each refresh."
    return body, decision


def attribution_report(folder):
    rows = read(folder, "comparison")
    body = cards([("Paid media", "$600,000"), ("Qualified / total leads",
                 "1,335 / 3,200"), ("Won / opportunities", "171 / 486")])
    body += section("Compare attribution models", '<label>Credit model <select id="model">'+''.join('<option>'+m+'</option>' for m in ["First touch", "Last touch", "Linear"])+'</select></label><div id="models">'+''.join('<div data-model="'+m+'">'+table(["Channel", "Credited wins", "Credited revenue", "Media CAC", "Gross-profit ROI"], [[r["channel"], f'{float(r["wins"]):.1f}', usd(
        r["revenue_usd"]), usd(r["media_cac"]), pct(r["gross_profit_roi"])] for r in rows if r["model"] == m])+'</div>' for m in ["First touch", "Last touch", "Linear"])+'</div><script>const select=document.querySelector("#model");function show(){document.querySelectorAll("[data-model]").forEach(el=>el.hidden=el.dataset.model!==select.value)}select.onchange=show;show()</script>')
    scenarios = read(folder, "budget_scenarios")
    body += section("A $10,000 reallocation test", "<p>Move spend from Display to Review Sites. Assume the removed dollars lose Display’s average linear-attributed yield. Vary the new dollars’ yield as a fraction of the Review Sites average. Total spend stays fixed.</p>" +
                    table(["Scenario", "Destination yield", "Revenue change", "Gross profit change"], [[r["label"], pct(r["destination_yield_fraction"]), usd(r["revenue_change_usd"]), usd(r["gross_profit_change_usd"])] for r in scenarios]))
    decision = "Review Sites receives $294,000 under first touch and $1,171,000 under last touch. Test a capped reallocation with a holdout before committing the full budget."
    return body, decision


def retention_report(folder):
    cohorts = read(folder, "cohorts")
    back = read(folder, "backtest")[0]
    body = cards([("Customers", "1,500"), ("Orders", "3,434"),
                 ("Q4 aggregate forecast error", pct(back["aggregate_error_pct"]))])
    matrix = []
    for c in range(1, 13):
        group = [r for r in cohorts if int(r["cohort_month"]) == c]
        row = [f"2025-{c:02}", group[0]["cohort_size"]]
        for age in range(12):
            if age < len(group):
                rate = float(group[age]["retention"])
                row.append(
                    f'<span style="display:block;padding:2px;background:rgba(55,150,125,{rate*.55:.2f})">{rate:.0%}</span>')
            else:
                row.append("—")
        matrix.append(row)
    body += section("Monthly purchase retention", '<p>Read across a row to follow a cohort from first purchase. Dashes mark months beyond December 2025.</p>' +
                    table(["First month", "Buyers"]+[f"M{j}" for j in range(12)], matrix))
    body += section("Customer segments and contribution", table(["Segment", "Customers", "Observed contribution", "Next 90 days", "Value per buyer through Mar"], [
                    [r["segment"], r["customers"], usd(r["observed_contribution_usd"]), usd(r["projected_90d_contribution_usd"]), usd(r["ltv_through_mar_per_customer"])] for r in read(folder, "segment_value")]))
    body += section("Forecast check", f'<p>For {int(back["eligible_customers"]):,} existing buyers, the unadjusted Q4 estimate was {usd(back["baseline_contribution"])}. Applying the {pct(back["carryover"])} historical carryover produced {usd(back["predicted_contribution"])} against {usd(back["actual_contribution"])} observed. Average absolute error was {usd(back["customer_mae_usd"])} per buyer, against mean realized contribution of {usd(float(back["actual_contribution"])/int(back["eligible_customers"]))}. Use this forecast for aggregate budgeting. Individual offer targeting needs separate validation.</p>')
    decision = "Test a win-back offer with a holdout among 319 at-risk repeat buyers. Use segment-level contribution to set the incentive budget."
    return body, decision


def audit_report(folder):
    exc = read(folder, "exceptions")
    daily = read(folder, "reconciliation")
    body = cards([("Failed checks across keys", str(len(exc))), ("Distinct affected keys", str(len(
        {(r["day"], r["account"], r["campaign"]) for r in exc}))), ("Convertible spend variance", "−$109.62")])
    body += section("Reconciliation by day", table(["Day", "Source USD", "Extract USD, convertible", "Variance USD", "Unpriced rows"], [
                    [r["day"], f'{float(r["ledger_usd"]):,.2f}', f'{float(r["convertible_extract_usd"]):,.2f}', f'{float(r["variance_usd"]):+,.2f}', r["unpriced_rows"]] for r in daily]))
    body += section("Exception queue", '<label>Severity <select id="severity"><option>All</option><option>High</option><option>Medium</option></select></label>'+table(["Rule", "Severity", "Day", "Account / campaign", "Evidence"], [
                    [r["rule"], r["severity"], r["day"], r["account"]+" / "+r["campaign"], r["evidence"]] for r in exc])+'<script>const severity=document.querySelector("#severity");severity.onchange=()=>severity.closest("section").querySelectorAll("tbody tr").forEach(row=>row.hidden=severity.value!=="All"&&row.cells[1].textContent!==severity.value)</script>')
    decision = "Hold the affected partitions, resolve the unmapped currency, then replay the missing and duplicate records. The daily ledger shows where netting hides gross discrepancies."
    return body, decision


REPORTS = {
    "02-api-pipeline": (pipeline_report, 'Automated marketing API pipeline', 'Can an agency refresh daily spend and replay corrections without double-counting?', 'One local HTTP source exposes an immutable snapshot per run. Pages contain up to 37 records. The extractor retries transient HTTP errors and commits the campaign-day upserts and watermark together. The fixture guarantees monotonic update times across snapshots. A live source with late or equal timestamps would need a lookback window or a stable change cursor.'),
    "03-attribution": (attribution_report, 'Marketing ROI and attribution', 'How much does a channel’s apparent return depend on which touch gets credit?', 'Independent B2B sample with one closed acquisition cohort and four paid channels. Every lead has an ordered path of one to four paid touches. Only first-channel identity affects qualification probability in the generator. Later touches receive credit under last-touch and linear models despite having no effect on simulated outcomes. The first-touch allocation recovers the simulated acquisition source. Linear credit is divided equally across touch events. Each win represents one new customer. Gross-profit ROI equals (credited revenue × 72% gross margin − media spend) / media spend. Model differences measure attribution sensitivity. Incremental impact requires an experiment.'),
    "04-retention": (retention_report, 'Customer retention and lifetime value', 'Which customers come back, and how much contribution can the retailer expect next quarter?', 'Independent e-commerce sample covering January–December 2025. Month 0 is the first purchase. Retention counts a customer again in every month with an order. RFM means recency, frequency and monetary value. Scores use fixed thresholds in the Python source. Value uses a 55% contribution margin. The estimate combines observed contribution with a three-month forecast and excludes subsequent value. Q2-to-Q3 carryover is trained on customers acquired before Q3, then frozen for the Q4 holdout. The forecast uses prior-quarter contribution for customers present at the forecast origin.'),
    "05-quality-audit": (audit_report, 'Marketing data quality audit', 'Can the reporting team trace a spend variance back to individual source records?', 'Independent March 2025 fixture. Platform records are the reference at date × account × campaign grain. Native amounts are integer minor units. Fixed illustrative USD rates are 1.08 per EUR and 1.27 per GBP. Each row is converted and rounded to cents. Unmapped currencies are excluded from convertible spend and counted separately. A key may fail multiple rules.'),
}


def main():
    entries = []
    for slug, (builder, title, question, method) in REPORTS.items():
        folder = ROOT / slug
        body, decision = builder(folder)
        body += section("Decision", decision)
        links = ' '.join(f'<a href="results/{f.name}">{f.name}</a>' for f in sorted(
            (folder/"results").glob("*")) if f.suffix in [".csv", ".json", ".log"])
        body += '<details open><summary>Assumptions and scope</summary><p>'+method + \
            '</p></details><details><summary>Download data and results</summary><p>' + \
                links+'</p></details><a href="../index.html">All projects</a>'
        (folder/"report.html").write_text(page(title,
                                               "FIELDLINE ANALYTICS  /  SYNTHETIC CASE STUDY", question, body), encoding="utf-8")
        entries.append(section(f'<a href="{slug}/report.html">{title}</a>', question))
    body = section('<a href="01-dashboard/index.html">B2B cross-channel marketing dashboard</a>',
                   'Which campaigns contribute to pipeline across a $2 million paid-media portfolio?')+"".join(entries)
    (ROOT/"index.html").write_text(page("Marketing analytics portfolio", "FIELDLINE ANALYTICS",
                                        "By <a style='color:white' href='https://github.com/prachi735'>Prachi Singh</a>, marketing analytics developer. Fieldline is the fictional agency in these five case studies.", body), encoding="utf-8")


if __name__ == "__main__":
    main()
