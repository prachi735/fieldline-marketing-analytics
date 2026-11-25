"""Create portable PBIP projects with refreshable, embedded case-study snapshots."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SCHEMA="https://developer.microsoft.com/json-schemas/fabric/item/"
def write(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding="utf-8")
def mquote(value):
    return '"'+value.replace('"','""')+'"'
def numeric(values):
    try:
        return all(float(x)==float(x) for x in values)
    except ValueError:
        return False
pages=[
[("Channel performance","channel_summary")],
[("Channel credit by model","comparison"),("Budget sensitivity","budget_scenarios")],
[("Retention by cohort age","cohorts"),("Value by segment","segment_value"),("Q4 validation","backtest")],
[("Reconciliation","reconciliation"),("Exception queue","exceptions"),("Scorecard","scorecard")]]
for i,project in enumerate(sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name[:2].isdigit())):
    base=project/"PowerBI"
    report=base/"Fieldline.Report"
    model=base/"Fieldline.SemanticModel"
    write(base/"Fieldline.pbip",{"version":"1.0","artifacts":[{"report":{"path":report.name}}],"settings":{"enableAutoRecovery":True}})
    write(report/"definition.pbir",{"version":"4.0","datasetReference":{"byPath":{"path":"../"+model.name}}})
    write(model/"definition.pbism",{"version":"1.0","settings":{}})
    d=report/"definition"
    write(d/"version.json",{"$schema":SCHEMA+"report/definition/versionMetadata/1.0.0/schema.json","version":"2.0.0"})
    write(d/"report.json",{"$schema":SCHEMA+"report/definition/report/2.1.0/schema.json","themeCollection":{"baseTheme":{"name":"CY24SU10","reportVersionAtImport":"5.59","type":"SharedResources"}}})
    order=[]
    tables=[]
    for idx,(caption,name) in enumerate(pages[i]):
        with (project/"results"/(name+".csv")).open() as f:
            rd=csv.DictReader(f)
            data=list(rd)
            names=rd.fieldnames
        nums=[numeric([r[col] for r in data]) for col in names]
        columns=[{"name":col,"dataType":"double" if n else "string","sourceColumn":col,"summarizeBy":"none"} for col,n in zip(names,nums)]
        for col,n in zip(columns,nums):
            if n:
                col["formatString"]="0.0%" if col["name"] in ("gross_profit_roi","aggregate_error_pct","retention","carryover","destination_yield_fraction") else "#,0.##"
        types=", ".join("#"+mquote(col)+"="+("number" if n else "text") for col,n in zip(names,nums))
        vals=["{"+", ".join(r[col] if n else mquote(r[col]) for col,n in zip(names,nums))+"}" for r in data]
        expression="#table(type table ["+types+"], {"+", ".join(vals)+"})"
        tables.append({"name":name,"columns":columns,"partitions":[{"name":name,"mode":"import","source":{"type":"m","expression":expression}}]})
        pageid=f"ReportSection{idx:012x}"
        order.append(pageid)
        pg=d/"pages"/pageid
        write(pg/"page.json",{"$schema":SCHEMA+"report/definition/page/2.0.0/schema.json","name":pageid,"displayName":caption,"displayOption":"FitToPage","height":720,"width":1280})
        projections=[{"field":{"Column":{"Expression":{"SourceRef":{"Entity":name}},"Property":col}},"queryRef":name+"."+col,"nativeQueryRef":col} for col in names]
        vid=f"{idx+1:020x}"
        write(pg/"visuals"/vid/"visual.json",{"$schema":SCHEMA+"report/definition/visualContainer/2.1.0/schema.json","name":vid,"position":{"x":15,"y":15,"z":0,"height":680,"width":1250,"tabOrder":0},"visual":{"visualType":"tableEx","query":{"queryState":{"Values":{"projections":projections}}},"visualContainerObjects":{"title":[{"properties":{"show":{"expr":{"Literal":{"Value":"true"}}},"text":{"expr":{"Literal":{"Value":"'"+caption+"'"}}}}}]}}})
    write(d/"pages"/"pages.json",{"$schema":SCHEMA+"report/definition/pagesMetadata/1.0.0/schema.json","pageOrder":order,"activePageName":order[0]})
    write(model/"model.bim",{"name":"Fieldline","compatibilityLevel":1567,"model":{"culture":"en-US","defaultPowerBIDataSourceVersion":"powerBI_V3","tables":tables}})

