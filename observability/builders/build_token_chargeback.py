import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = os.path.join(_HERE, "..", "dashboards")

import json

SUB = "e4e9074e-0238-41e6-929e-edda76b67e79"
LAW = (f"/subscriptions/{SUB}/resourceGroups/gaih-prd01-mon-rg/providers/"
       "Microsoft.OperationalInsights/workspaces/gaih-prd01-law0")
DS = {"type": "grafana-azure-monitor-datasource", "uid": "azure-monitor-oob"}

# AppMetrics carries Product ID / Subscription ID / Model / Region / API ID
# alongside the prompt+completion split, for every model family.
BASE = ("AppMetrics\n"
        "| where Name in ('Prompt Tokens', 'Completion Tokens')\n"
        "| extend P = todynamic(Properties)\n"
        "| extend Product = tostring(P['Product ID']), Consumer = tostring(P['Subscription ID']),\n"
        "         Model = tostring(P['Model']), Region = tostring(P['Region']), Api = tostring(P['API ID'])\n"
        "| where isnotempty(Model)\n")

FILT = ("| where '*' in (${product:singlequote}) or Product in (${product:singlequote})\n"
        "| where '*' in (${model:singlequote}) or Model in (${model:singlequote})\n")

RATE_CARD = """// ===================================================================
// RATE CARD - EUR per 1,000,000 tokens
// DERIVED FROM ACTUAL AZURE BILLING (Cost Management, Jul 2026).
// Each rate = billed cost / billed quantity for that model's meters.
// Meters quoted per 1K tokens were normalised to per 1M.
// These are effective actual rates, not list prices. Re-derive when
// your commercial terms change. Models showing 0.0 had no billable
// meter in the period - their cost will read 0 and 'Rate set' = no.
// ===================================================================
let Currency = 'EUR';
let Rates = datatable(Model:string, InPer1M:real, OutPer1M:real)[
%s
];
"""


def build_rates():
    import json as _j
    rows = _j.load(open(os.path.join(_HERE, "rates.json")))
    have = {r[0] for r in rows}
    models = [m.strip() for m in open(os.path.join(_HERE, "models.txt")).read().splitlines() if m.strip()]
    out = [f'    "{m}", {i}, {o}' for m, i, o in rows]
    out += [f'    "{m}", 0.0, 0.0' for m in models if m not in have]
    return ",\n".join(out)


RATES = RATE_CARD % build_rates()


def q(query, fmt="time_series", ref="A"):
    return [{
        "refId": ref, "queryType": "Azure Log Analytics", "datasource": DS,
        "subscription": SUB, "subscriptions": [],
        "azureLogAnalytics": {"query": query, "resource": LAW, "resultFormat": fmt,
                              "dashboardTime": True, "timeColumn": "TimeGenerated"},
    }]


def stat(title, desc, query, unit, steps, gp, calc="sum", graph="area",
         color_mode="value", decimals=None):
    return {
        "type": "stat", "title": title, "description": desc, "datasource": DS,
        "gridPos": gp, "targets": q(query),
        "fieldConfig": {"defaults": {
            "unit": unit, "decimals": decimals, "color": {"mode": "thresholds"},
            "thresholds": {"mode": "absolute", "steps": steps}, "mappings": []}, "overrides": []},
        "options": {"colorMode": color_mode, "graphMode": graph, "justifyMode": "auto",
                    "orientation": "auto", "textMode": "auto", "wideLayout": True,
                    "showPercentChange": False,
                    "reduceOptions": {"calcs": [calc], "fields": "", "values": False}},
    }


def ts(title, desc, query, unit, gp, stack=None):
    custom = {"drawStyle": "line", "lineInterpolation": "smooth", "lineWidth": 2,
              "fillOpacity": 20, "gradientMode": "opacity", "showPoints": "never",
              "spanNulls": True, "axisSoftMin": 0,
              "scaleDistribution": {"type": "linear"},
              "hideFrom": {"legend": False, "tooltip": False, "viz": False}}
    if stack:
        custom.update({"stacking": {"mode": stack, "group": "A"},
                       "fillOpacity": 70, "lineWidth": 1})
    return {
        "type": "timeseries", "title": title, "description": desc, "datasource": DS,
        "gridPos": gp, "targets": q(query),
        "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "palette-classic"},
                                     "custom": custom,
                                     "thresholds": {"mode": "absolute",
                                                    "steps": [{"color": "green", "value": None}]}},
                        "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "bottom",
                               "showLegend": True, "calcs": ["sum"]},
                    "tooltip": {"mode": "multi", "sort": "desc"}},
    }


def bar(title, desc, query, unit, gp, horiz=True):
    return {
        "type": "barchart", "title": title, "description": desc, "datasource": DS,
        "gridPos": gp, "targets": q(query, "table"),
        "fieldConfig": {"defaults": {
            "unit": unit, "color": {"mode": "palette-classic"},
            "custom": {"lineWidth": 1, "fillOpacity": 85, "gradientMode": "hue",
                       "axisPlacement": "auto",
                       "hideFrom": {"legend": False, "tooltip": False, "viz": False}},
            "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]}},
            "overrides": []},
        "options": {"orientation": "horizontal" if horiz else "vertical",
                    "xTickLabelRotation": 0, "xTickLabelSpacing": 100,
                    "showValue": "auto", "stacking": "none",
                    "legend": {"displayMode": "hidden", "placement": "bottom", "showLegend": False},
                    "tooltip": {"mode": "single", "sort": "none"}},
    }


def table(title, desc, query, gp, overrides, sort_col=None):
    opts = {"showHeader": True, "cellHeight": "sm",
            "footer": {"show": True, "reducer": ["sum"], "countRows": False, "fields": ""}}
    if sort_col:
        opts["sortBy"] = [{"displayName": sort_col, "desc": True}]
    return {
        "type": "table", "title": title, "description": desc, "datasource": DS,
        "gridPos": gp, "targets": q(query, "table"),
        "fieldConfig": {"defaults": {
            "custom": {"align": "auto", "cellOptions": {"type": "auto"},
                       "inspect": False, "filterable": True},
            "color": {"mode": "thresholds"},
            "thresholds": {"mode": "absolute", "steps": [{"color": "text", "value": None}]}},
            "overrides": overrides},
        "options": opts,
    }


def text(title, content, gp):
    return {"type": "text", "title": title, "gridPos": gp,
            "options": {"mode": "markdown", "content": content}}


def row(title, gp, collapsed=False, panels=None):
    return {"type": "row", "title": title, "gridPos": gp,
            "collapsed": collapsed, "panels": panels or []}


def grad(field, steps, unit="short", decimals=0, w=None):
    props = [{"id": "unit", "value": unit}, {"id": "decimals", "value": decimals},
             {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "gradient"}},
             {"id": "thresholds", "value": {"mode": "absolute", "steps": steps}}]
    if w:
        props.append({"id": "custom.width", "value": w})
    return {"matcher": {"id": "byName", "options": field}, "properties": props}


def gaugecell(field, steps, unit="percent", decimals=2, mx=100):
    return {"matcher": {"id": "byName", "options": field}, "properties": [
        {"id": "unit", "value": unit}, {"id": "decimals", "value": decimals},
        {"id": "custom.cellOptions", "value": {"type": "gauge", "mode": "gradient",
                                               "valueDisplayMode": "text"}},
        {"id": "thresholds", "value": {"mode": "absolute", "steps": steps}},
        {"id": "max", "value": mx}, {"id": "min", "value": 0}]}


def w(field, px):
    return {"matcher": {"id": "byName", "options": field},
            "properties": [{"id": "custom.width", "value": px}]}


BLUE = [{"color": "blue", "value": None}]
GREEN = [{"color": "green", "value": None}]
SHARE = [{"color": "blue", "value": None}, {"color": "orange", "value": 25},
         {"color": "red", "value": 50}]
OUTR = [{"color": "green", "value": None}, {"color": "yellow", "value": 5},
        {"color": "orange", "value": 15}]


def dlink(field, title, uid, slug, var, width=None):
    """Data link on a table field: click a value, land on another dashboard
    filtered to it, carrying the current time range."""
    props = [{"id": "links", "value": [{
        "title": title,
        "url": f"/d/{uid}/{slug}?var-{var}=${{__value.text}}&${{__url_time_range}}",
        "targetBlank": False}]}]
    if width:
        props.append({"id": "custom.width", "value": width})
    return {"matcher": {"id": "byName", "options": field}, "properties": props}


panels = []

# ================= AT A GLANCE =================
panels.append(row("Consumption at a Glance", {"h": 1, "w": 24, "x": 0, "y": 0}))

panels.append(stat("Total Tokens", "All prompt and completion tokens through the model gateway in the selected window, across every model family.",
                   BASE + FILT + "| summarize Tokens=sum(Sum) by bin(TimeGenerated, 1h)\n| order by TimeGenerated asc",
                   "short", BLUE, {"h": 5, "w": 4, "x": 0, "y": 1}))

panels.append(stat("Prompt Tokens", "Input tokens. Usually the cheaper half of the bill, but the larger volume.",
                   BASE + FILT + "| where Name == 'Prompt Tokens'\n| summarize Tokens=sum(Sum) by bin(TimeGenerated, 1h)\n| order by TimeGenerated asc",
                   "short", BLUE, {"h": 5, "w": 4, "x": 4, "y": 1}))

panels.append(stat("Completion Tokens", "Generated tokens. Typically priced several times higher than input, so this drives cost far more than its volume suggests.",
                   BASE + FILT + "| where Name == 'Completion Tokens'\n| summarize Tokens=sum(Sum) by bin(TimeGenerated, 1h)\n| order by TimeGenerated asc",
                   "short", BLUE, {"h": 5, "w": 4, "x": 8, "y": 1}))

panels.append(stat("Output Share", "Completion tokens as a percentage of total. The single best cost predictor available without prices: a rising share means spend grows faster than volume.",
                   BASE + FILT +
                   "| summarize Prompt=sumif(Sum, Name=='Prompt Tokens'), Completion=sumif(Sum, Name=='Completion Tokens') by bin(TimeGenerated, 1h)\n"
                   "| project TimeGenerated, OutputShare = 100.0 * Completion / iff(Prompt+Completion == 0, 1.0, Prompt+Completion)\n"
                   "| order by TimeGenerated asc",
                   "percent", OUTR, {"h": 5, "w": 4, "x": 12, "y": 1}, calc="mean", decimals=2))

panels.append(stat("Active Products", "Distinct APIM products consuming models in the window. This is the chargeback population.",
                   BASE + FILT + "| summarize Products=dcount(Product)",
                   "short", BLUE, {"h": 5, "w": 4, "x": 16, "y": 1}, calc="lastNotNull", graph="none"))

panels.append(stat("Active Models", "Distinct model deployments receiving traffic. Compare with the total deployed estate to spot models nobody uses.",
                   BASE + FILT + "| summarize Models=dcount(Model)",
                   "short", BLUE, {"h": 5, "w": 4, "x": 20, "y": 1}, calc="lastNotNull", graph="none"))

# ================= CHARGEBACK BY PRODUCT =================
panels.append(row("Chargeback by Product", {"h": 1, "w": 24, "x": 0, "y": 6}))

panels.append(bar("Token Share by Product",
                  "Total tokens per APIM product. This is the allocation basis for chargeback.",
                  BASE + FILT + "| summarize Tokens=sum(Sum) by Product\n| top 15 by Tokens desc",
                  "short", {"h": 10, "w": 10, "x": 0, "y": 7}))

panels.append(ts("Product Consumption Trend",
                 "Token consumption over time per product, stacked. Use it to spot a product whose usage is climbing before it shows up on an invoice.",
                 BASE + FILT + "| summarize Tokens=sum(Sum) by bin(TimeGenerated, 1h), Product\n| order by TimeGenerated asc",
                 "short", {"h": 10, "w": 14, "x": 10, "y": 7}, stack="normal"))

panels.append(table("Product Chargeback Detail",
                    "Per-product allocation basis. APM ID is parsed from the product name where present. Output share flags products whose usage skews to expensive generated tokens.",
                    BASE + FILT +
                    "| summarize Prompt=sumif(Sum, Name=='Prompt Tokens'), Completion=sumif(Sum, Name=='Completion Tokens'),\n"
                    "            Models=dcount(Model), Consumers=dcount(Consumer) by Product\n"
                    "| extend Total = Prompt + Completion\n"
                    "| extend ['Output %'] = round(100.0 * Completion / iff(Total==0, 1.0, Total), 2)\n"
                    "| extend ['APM ID'] = extract(@'([0-9]{5,6})', 1, Product)\n"
                    "| extend ['Share %'] = round(100.0 * Total / toscalar(\n"
                    "      AppMetrics | where Name in ('Prompt Tokens','Completion Tokens') | summarize sum(Sum)), 2)\n"
                    "| project Product, ['APM ID'], Total, Prompt, Completion, ['Output %'], ['Share %'], Models, Consumers\n"
                    "| order by Total desc",
                    {"h": 11, "w": 24, "x": 0, "y": 17},
                    [w("Product", 420), grad("Total", BLUE, "short", 0, 130),
                     gaugecell("Share %", SHARE), gaugecell("Output %", OUTR, mx=25),
                     w("APM ID", 100)],
                    sort_col="Total"))

# ================= MODEL ECONOMICS =================
panels.append(row("Model Economics", {"h": 1, "w": 24, "x": 0, "y": 28}))

panels.append(bar("Tokens by Model",
                  "Total tokens per model deployment. Concentration here tells you which models actually matter commercially.",
                  BASE + FILT + "| summarize Tokens=sum(Sum) by Model\n| top 15 by Tokens desc",
                  "short", {"h": 10, "w": 10, "x": 0, "y": 29}))

panels.append(ts("Input vs Output Tokens Over Time",
                 "Prompt against completion tokens. Divergence matters: output tokens are priced far higher, so a rising completion line raises cost faster than the volume implies.",
                 BASE + FILT +
                 "| summarize Prompt=sumif(Sum, Name=='Prompt Tokens'), Completion=sumif(Sum, Name=='Completion Tokens') by bin(TimeGenerated, 1h)\n"
                 "| order by TimeGenerated asc",
                 "short", {"h": 10, "w": 14, "x": 10, "y": 29}))

panels.append(table("Model Consumption Detail",
                    "Per-model token split with the products and regions consuming each. Output share is the cost-weighting signal to watch until rates are entered.",
                    BASE + FILT +
                    "| summarize Prompt=sumif(Sum, Name=='Prompt Tokens'), Completion=sumif(Sum, Name=='Completion Tokens'),\n"
                    "            Products=dcount(Product), Regions=dcount(Region) by Model\n"
                    "| extend Total = Prompt + Completion\n"
                    "| extend ['Output %'] = round(100.0 * Completion / iff(Total==0, 1.0, Total), 2)\n"
                    "| project Model, Total, Prompt, Completion, ['Output %'], Products, Regions\n"
                    "| order by Total desc",
                    {"h": 11, "w": 24, "x": 0, "y": 39},
                    [dlink("Model", "Gateway health for this deployment", "genai-model-operations", "genai-hub-model-operations", "deployment", width=340),
                     grad("Total", BLUE, "short", 0, 130),
                     gaugecell("Output %", OUTR, mx=25)],
                    sort_col="Total"))

# ================= RATE CARD & COST (collapsed) =================
cost_panels = [
    text("Cost coverage - read this first", """
### Rates are real. Coverage is not complete.

Rates below are **derived from actual Azure billing** (Cost Management, Jul 2026), in **EUR per 1M tokens**, split input/output.

### What is missing

These panels are built on `AppMetrics`, which **does not carry any Anthropic/Claude model**. Claude was about **EUR 36k of EUR 66k actual model spend in July** - so cost here covers OpenAI, Kimi and embeddings **only**.

Validated against billing for 1-30 Jul:

| | EUR |
|---|---|
| Estimated here | 12,502 |
| Actual (all models) | 66,022 |
| Actual (excl. Claude) | ~30,000 |

The remaining gap after Claude is **long-context and cache-write meters**, which are billed at premium rates this model does not represent.

### Why Claude cannot simply be added

`GatewayLlmLogs` is the only log source with Claude tokens and it is **incomplete**: over 30 days it reports 472M prompt tokens and **zero** completion and **zero** cached tokens, while billing shows billions of cache-hit tokens. It is not reliable for costing.

**Treat these figures as a directional lower bound for OpenAI-family models, not a bill.**
Azure Cost Management remains the source of truth.
""", {"h": 9, "w": 7, "x": 0, "y": 50}),

    table("Estimated Cost by Product",
          "Cost per product using rates derived from actual Azure billing. EXCLUDES all Claude models (AppMetrics carries no Anthropic data) and does not model long-context or cache-write premiums, so totals run well below the real bill. Directional only.",
          RATES + BASE + FILT +
          "| summarize Prompt=sumif(Sum, Name=='Prompt Tokens'), Completion=sumif(Sum, Name=='Completion Tokens') by Product, Model\n"
          "| join kind=leftouter Rates on Model\n"
          "| extend InPer1M = todouble(coalesce(InPer1M, 0.0)), OutPer1M = todouble(coalesce(OutPer1M, 0.0))\n"
          "| extend ['Input cost'] = Prompt / 1000000.0 * InPer1M,\n"
          "         ['Output cost'] = Completion / 1000000.0 * OutPer1M\n"
          "| summarize ['Input cost']=round(sum(['Input cost']), 2), ['Output cost']=round(sum(['Output cost']), 2),\n"
          "            Tokens=sum(Prompt+Completion) by Product\n"
          "| extend ['Total cost'] = round(['Input cost'] + ['Output cost'], 2)\n"
          "| project Product, ['Total cost'], ['Input cost'], ['Output cost'], Tokens\n"
          "| order by ['Total cost'] desc, Tokens desc",
          {"h": 9, "w": 17, "x": 7, "y": 50},
          [w("Product", 400), grad("Total cost", GREEN, "currencyEUR", 2, 130),
           grad("Tokens", BLUE, "short", 0, 130)],
          sort_col="Total cost"),

    table("Estimated Cost by Model",
          "Cost per model using rates derived from actual Azure billing (EUR per 1M tokens). Claude models are absent entirely - AppMetrics does not emit them. Rate set = no means no billable meter was found for that deployment.",
          RATES + BASE + FILT +
          "| summarize Prompt=sumif(Sum, Name=='Prompt Tokens'), Completion=sumif(Sum, Name=='Completion Tokens') by Model\n"
          "| join kind=leftouter Rates on Model\n"
          "| extend InPer1M = todouble(coalesce(InPer1M, 0.0)), OutPer1M = todouble(coalesce(OutPer1M, 0.0))\n"
          "| extend ['Input cost'] = round(Prompt / 1000000.0 * InPer1M, 2),\n"
          "         ['Output cost'] = round(Completion / 1000000.0 * OutPer1M, 2)\n"
          "| extend Tokens = Prompt + Completion\n"
          "| extend ['Total cost'] = round(['Input cost'] + ['Output cost'], 2)\n"
          "| extend ['Cost per 1M'] = round(['Total cost'] / iff(Tokens==0, 1.0, Tokens / 1000000.0), 2)\n"
          "| extend ['Rate set'] = iff(InPer1M == 0.0 and OutPer1M == 0.0, 'no', 'yes')\n"
          "| project Model, ['Total cost'], ['Input cost'], ['Output cost'], ['Cost per 1M'], Tokens, ['Rate set']\n"
          "| order by Tokens desc",
          {"h": 11, "w": 24, "x": 0, "y": 59},
          [dlink("Model", "Gateway health for this deployment", "genai-model-operations", "genai-hub-model-operations", "deployment", width=340),
           grad("Total cost", GREEN, "currencyEUR", 2, 130),
           grad("Tokens", BLUE, "short", 0, 130),
           {"matcher": {"id": "byName", "options": "Rate set"}, "properties": [
               {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
               {"id": "mappings", "value": [{"type": "value", "options": {
                   "no": {"color": "orange", "index": 0},
                   "yes": {"color": "green", "index": 1}}}]},
               {"id": "custom.width", "value": 100}]}],
          sort_col="Tokens"),
]
panels.append(row("Estimated Cost", {"h": 1, "w": 24, "x": 0, "y": 49},
                  collapsed=False, panels=None))
panels.extend(cost_panels)

# ================= REGION & API (collapsed) =================
region_panels = [
    bar("Tokens by Region", "Where model traffic is actually served. Useful for data-residency review and for spotting cross-region routing.",
        BASE + FILT + "| summarize Tokens=sum(Sum) by Region\n| order by Tokens desc",
        "short", {"h": 9, "w": 8, "x": 0, "y": 51}),
    bar("Tokens by API", "Which gateway API surface the consumption arrives through.",
        BASE + FILT + "| summarize Tokens=sum(Sum) by Api\n| top 12 by Tokens desc",
        "short", {"h": 9, "w": 8, "x": 8, "y": 51}),
    table("Consumer Detail",
          "Token consumption per APIM subscription, one level below product. Use it to find the specific application inside a product that drives the bill.",
          BASE + FILT +
          "| summarize Prompt=sumif(Sum, Name=='Prompt Tokens'), Completion=sumif(Sum, Name=='Completion Tokens'),\n"
          "            Models=dcount(Model) by Consumer, Product\n"
          "| extend Total = Prompt + Completion\n"
          "| project Consumer, Product, Total, Prompt, Completion, Models\n"
          "| order by Total desc",
          {"h": 9, "w": 8, "x": 16, "y": 51},
          [dlink("Consumer", "Gateway health for this consumer", "genai-model-operations", "genai-hub-model-operations", "consumer", width=260),
           grad("Total", BLUE, "short", 0, 120)],
          sort_col="Total"),
]
panels.append(row("Region, API and Consumer Detail", {"h": 1, "w": 24, "x": 0, "y": 50},
                  collapsed=True, panels=region_panels))


def var(name, label, query, desc):
    return {"name": name, "label": label, "description": desc, "type": "query",
            "datasource": DS,
            "query": {"refId": "A", "queryType": "Azure Log Analytics",
                      "azureLogAnalytics": {"query": query, "resource": LAW},
                      "subscription": SUB},
            "definition": label, "refresh": 1, "multi": True, "includeAll": True,
            "allValue": "'*'",
            "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
            "options": [], "sort": 1, "hide": 0}


dashboard = {
    "uid": "genai-token-chargeback",
    "title": "GenAI Hub - Token Economics and Chargeback",
    "description": ("Live token consumption and chargeback across every model family, built on the "
                    "product / consumer / model / region dimensions carried in AppMetrics. Denominated "
                    "in tokens: an editable rate card in the Rate Card section turns on cost without "
                    "guessing prices."),
    "tags": ["genai-hub", "production", "cost", "chargeback", "finops"],
    "timezone": "browser", "editable": True, "graphTooltip": 1,
    "refresh": "30m", "schemaVersion": 39,
    "time": {"from": "now-30d", "to": "now"},
    "timepicker": {"refresh_intervals": ["5m", "15m", "30m", "1h", "6h", "12h"]},
    "templating": {"list": [
        var("product", "Product",
            BASE + "| distinct Product\n| where isnotempty(Product)\n| order by Product asc",
            "Filter the dashboard to one or more APIM products."),
        var("model", "Model",
            BASE + "| distinct Model\n| order by Model asc",
            "Filter the dashboard to one or more model deployments."),
    ]},
    "links": [{"title": "GenAI Hub dashboards", "type": "dashboards", "tags": ["genai-hub"],
               "asDropdown": True, "icon": "external link", "includeVars": False,
               "keepTime": True, "targetBlank": False, "tooltip": "", "url": ""}],
    "panels": panels,
}

out = os.path.join(_OUT, "genai-token-chargeback.json")
json.dump(dashboard, open(out, "w"), indent=2)

flat = []
for p in panels:
    flat.append(p)
    flat.extend(p.get("panels", []))
print("panels:", len(flat), "| rows:", sum(1 for p in flat if p["type"] == "row"))
print("rate card models:", RATES.count(", 0.0, 0.0"))
print("written:", out)
