import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = os.path.join(_HERE, "..", "dashboards")

import json

SUB = "e4e9074e-0238-41e6-929e-edda76b67e79"
LAW = (f"/subscriptions/{SUB}/resourceGroups/gaih-prd01-mon-rg/providers/"
       "Microsoft.OperationalInsights/workspaces/gaih-prd01-law0")
DS = {"type": "grafana-azure-monitor-datasource", "uid": "azure-monitor-oob"}

# Every scan writes a complete snapshot, so always pin to the newest ScanId or
# costs multiply across scans. Filter on UsageDate (real spend date), NOT
# TimeGenerated (ingestion time) - hence dashboardTime is off for these panels.
LATEST = ("let Latest = toscalar(GenAIModelCost_CL "
          "| summarize arg_max(TimeGenerated, ScanId) | project ScanId);\n")
DAILY = (LATEST + "GenAIModelCost_CL\n| where ScanId == Latest and Grain == 'Daily'\n"
         "| where UsageDate >= $__timeFrom and UsageDate < $__timeTo\n")
MONTHLY = (LATEST + "GenAIModelCost_CL\n| where ScanId == Latest and Grain == 'Monthly'\n")
MODELCATS = "'Foundry Models', 'SaaS', 'Cognitive Services'"

TOKENTYPE = (
    "| extend TokenType = case(\n"
    "    Meter has 'cache-hit' or Meter has 'cchd' or Meter has ' cd ' or Meter has 'Cd Inp' or Meter has 'cached', 'Cache read',\n"
    "    Meter has 'cache-write' or Meter has 'Cd Wr', 'Cache write',\n"
    "    Meter has 'output' or Meter has ' opt ' or Meter has 'Outp' or Meter has 'outpt', 'Output',\n"
    "    Meter has 'input' or Meter has ' inp ' or Meter has 'Inp', 'Input', 'Other')\n")


def q(query, fmt="time_series", ref="A"):
    return [{"refId": ref, "queryType": "Azure Log Analytics", "datasource": DS,
             "subscription": SUB, "subscriptions": [],
             "azureLogAnalytics": {"query": query, "resource": LAW,
                                   "resultFormat": fmt, "dashboardTime": False}}]


def stat(title, desc, query, gp, unit="currencyEUR", steps=None, calc="lastNotNull",
         graph="none", decimals=0, color_mode="value"):
    return {"type": "stat", "title": title, "description": desc, "datasource": DS,
            "gridPos": gp, "targets": q(query, "table"),
            "fieldConfig": {"defaults": {
                "unit": unit, "decimals": decimals, "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute",
                               "steps": steps or [{"color": "blue", "value": None}]},
                "mappings": []}, "overrides": []},
            "options": {"colorMode": color_mode, "graphMode": graph,
                        "justifyMode": "auto", "orientation": "auto",
                        "textMode": "auto", "wideLayout": True,
                        "showPercentChange": False,
                        "reduceOptions": {"calcs": [calc], "fields": "", "values": False}}}


def ts(title, desc, query, gp, stack="normal", unit="currencyEUR"):
    custom = {"drawStyle": "line", "lineInterpolation": "smooth", "lineWidth": 1,
              "fillOpacity": 75, "gradientMode": "opacity", "showPoints": "never",
              "spanNulls": True, "axisSoftMin": 0,
              "stacking": {"mode": stack, "group": "A"},
              "scaleDistribution": {"type": "linear"},
              "hideFrom": {"legend": False, "tooltip": False, "viz": False}}
    return {"type": "timeseries", "title": title, "description": desc, "datasource": DS,
            "gridPos": gp, "targets": q(query),
            "fieldConfig": {"defaults": {"unit": unit,
                                         "color": {"mode": "palette-classic"},
                                         "custom": custom,
                                         "thresholds": {"mode": "absolute",
                                                        "steps": [{"color": "green", "value": None}]}},
                            "overrides": []},
            "options": {"legend": {"displayMode": "table", "placement": "bottom",
                                   "showLegend": True, "calcs": ["sum"]},
                        "tooltip": {"mode": "multi", "sort": "desc"}}}


def bar(title, desc, query, gp, unit="currencyEUR"):
    return {"type": "barchart", "title": title, "description": desc, "datasource": DS,
            "gridPos": gp, "targets": q(query, "table"),
            "fieldConfig": {"defaults": {
                "unit": unit, "color": {"mode": "palette-classic"},
                "custom": {"lineWidth": 1, "fillOpacity": 85, "gradientMode": "hue",
                           "hideFrom": {"legend": False, "tooltip": False, "viz": False}},
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]}},
                "overrides": []},
            "options": {"orientation": "horizontal", "showValue": "auto",
                        "stacking": "none", "xTickLabelRotation": 0,
                        "xTickLabelSpacing": 100,
                        "legend": {"displayMode": "hidden", "placement": "bottom",
                                   "showLegend": False},
                        "tooltip": {"mode": "single", "sort": "none"}}}


def table(title, desc, query, gp, overrides, sort_col=None):
    opts = {"showHeader": True, "cellHeight": "sm",
            "footer": {"show": True, "reducer": ["sum"], "countRows": False, "fields": ""}}
    if sort_col:
        opts["sortBy"] = [{"displayName": sort_col, "desc": True}]
    return {"type": "table", "title": title, "description": desc, "datasource": DS,
            "gridPos": gp, "targets": q(query, "table"),
            "fieldConfig": {"defaults": {
                "custom": {"align": "auto", "cellOptions": {"type": "auto"},
                           "inspect": False, "filterable": True},
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": [{"color": "text", "value": None}]}},
                "overrides": overrides},
            "options": opts}


def row(title, gp, collapsed=False, panels=None):
    return {"type": "row", "title": title, "gridPos": gp,
            "collapsed": collapsed, "panels": panels or []}


def grad(field, steps, unit="currencyEUR", dec=2, w=None):
    p = [{"id": "unit", "value": unit}, {"id": "decimals", "value": dec},
         {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "gradient"}},
         {"id": "thresholds", "value": {"mode": "absolute", "steps": steps}}]
    if w:
        p.append({"id": "custom.width", "value": w})
    return {"matcher": {"id": "byName", "options": field}, "properties": p}


def w(field, px):
    return {"matcher": {"id": "byName", "options": field},
            "properties": [{"id": "custom.width", "value": px}]}


BLUE = [{"color": "blue", "value": None}]
GREEN = [{"color": "green", "value": None}]
FRESH = [{"color": "green", "value": None}, {"color": "yellow", "value": 30},
         {"color": "red", "value": 48}]

panels = []
panels.append(row("Actual Spend from Azure Billing", {"h": 1, "w": 24, "x": 0, "y": 0}))

panels.append(stat(
    "Total Azure Spend", "All Azure spend in the selected window, from Cost Management. Follows the time picker via the real usage date.",
    DAILY + "| summarize Cost = round(sum(Cost), 2)",
    {"h": 5, "w": 5, "x": 0, "y": 1}, steps=BLUE))

panels.append(stat(
    "Model Spend", "Spend on model inference only (Foundry Models, SaaS model plans, Cognitive Services). Includes Anthropic, which token-based estimates cannot see.",
    DAILY + f"| where MeterCategory in ({MODELCATS})\n| summarize Cost = round(sum(Cost), 2)",
    {"h": 5, "w": 5, "x": 5, "y": 1}, steps=GREEN))

panels.append(stat(
    "Platform and Infrastructure", "Everything that is not model inference - APIM, Container Apps, storage, networking, databases.",
    DAILY + f"| where MeterCategory !in ({MODELCATS})\n| summarize Cost = round(sum(Cost), 2)",
    {"h": 5, "w": 5, "x": 10, "y": 1}, steps=BLUE))

panels.append(stat(
    "Model Share of Spend", "Model inference as a percentage of total Azure spend.",
    DAILY + f"| summarize Total = sum(Cost), Model = sumif(Cost, MeterCategory in ({MODELCATS}))\n"
    "| project Share = round(100.0 * Model / iff(Total == 0, 1.0, Total), 1)",
    {"h": 5, "w": 4, "x": 15, "y": 1}, unit="percent", decimals=1, steps=BLUE))

panels.append(stat(
    "Data Age", "Hours since the cost pipeline last refreshed. The scan runs daily; anything above 48h means gaih-prd01-model-cost-scan has stopped.",
    "GenAIModelCost_CL | summarize Age = round(datetime_diff('minute', now(), max(TimeGenerated)) / 60.0, 1)",
    {"h": 5, "w": 5, "x": 19, "y": 1}, unit="h", decimals=1, steps=FRESH,
    color_mode="background_solid"))

panels.append(ts(
    "Daily Model Spend by Family",
    "Actual daily model cost per model family, stacked. This is billed spend, not a token estimate, so Anthropic and long-context/cache premiums are all included.",
    DAILY + f"| where MeterCategory in ({MODELCATS})\n"
    "| extend Family = iff(isempty(MeterSubCategory), MeterCategory, MeterSubCategory)\n"
    "| summarize Cost = sum(Cost) by TimeGenerated = UsageDate, Family\n"
    "| order by TimeGenerated asc",
    {"h": 10, "w": 14, "x": 0, "y": 6}))

panels.append(bar(
    "Model Spend by Family",
    "Total actual spend per model family in the selected window.",
    DAILY + f"| where MeterCategory in ({MODELCATS})\n"
    "| extend Family = iff(isempty(MeterSubCategory), MeterCategory, MeterSubCategory)\n"
    "| summarize Cost = round(sum(Cost), 2) by Family\n| top 14 by Cost desc",
    {"h": 10, "w": 10, "x": 14, "y": 6}))

panels.append(table(
    "Spend by Token Type",
    "Where model money actually goes, split into input, output, cache read and cache write. Sourced from meter-level detail. Cache read being large is evidence prompt caching is working, not idle.",
    MONTHLY + f"| where MeterCategory in ({MODELCATS})\n" + TOKENTYPE +
    "| extend Family = iff(isempty(MeterSubCategory), MeterCategory, MeterSubCategory)\n"
    "| summarize Cost = round(sum(Cost), 2), Units = round(sum(UsageQuantity), 1) by Family, TokenType\n"
    "| order by Cost desc",
    {"h": 11, "w": 12, "x": 0, "y": 16},
    [w("Family", 220), grad("Cost", GREEN, "currencyEUR", 2, 130),
     grad("Units", BLUE, "short", 1, 120)],
    sort_col="Cost"))

panels.append(table(
    "Spend by Azure Service",
    "Full actual spend by Azure meter category in the selected window - the complete bill, not just models.",
    DAILY + "| summarize Cost = round(sum(Cost), 2) by ['Azure service'] = MeterCategory, "
    "['Sub category'] = MeterSubCategory\n| order by Cost desc | take 40",
    {"h": 11, "w": 12, "x": 12, "y": 16},
    [w("Azure service", 210), w("Sub category", 230),
     grad("Cost", BLUE, "currencyEUR", 2, 130)],
    sort_col="Cost"))

dashboard = {
    "uid": "genai-actual-cost",
    "title": "GenAI Hub - Actual Cost (Live from Azure Billing)",
    "description": ("Real billed Azure spend, refreshed daily by the gaih-prd01-model-cost-scan "
                    "Logic App into GenAIModelCost_CL. Covers every model family including "
                    "Anthropic, plus platform and infrastructure. Panels filter on the real usage "
                    "date, so the time picker works. Source of truth for cost - token-derived "
                    "estimates elsewhere are directional only."),
    "tags": ["genai-hub", "production", "cost", "finops", "billing"],
    "timezone": "browser", "editable": True, "graphTooltip": 1,
    "refresh": "1h", "schemaVersion": 39,
    "time": {"from": "now-60d", "to": "now"},
    "templating": {"list": []},
    "links": [{"title": "GenAI Hub dashboards", "type": "dashboards", "tags": ["genai-hub"],
               "asDropdown": True, "icon": "external link", "includeVars": False,
               "keepTime": True, "targetBlank": False, "tooltip": "", "url": ""}],
    "panels": panels,
}

out = os.path.join(_OUT, "genai-actual-cost.json")
json.dump(dashboard, open(out, "w"), indent=2)
print("panels:", len([p for p in panels if p["type"] != "row"]))
print("written:", out)
