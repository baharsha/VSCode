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

# ---------------------------------------------------------------------------
# COST ALLOCATION - actual billed cost, distributed across products.
#
# We do NOT estimate cost from tokens. Total always reconciles to the real
# Azure bill because we start from it and divide it up.
#
#   Claude  -> allocated by share of anthropic-api REQUESTS. AppMetrics carries
#              no Anthropic rows and GatewayLlmLogs has deploymentName_s empty
#              on ~64% of rows, so requests are the only complete Claude signal.
#   OpenAI  -> allocated by share of TOKENS from AppMetrics, which is complete
#              and more precise for that family.
# ---------------------------------------------------------------------------
ALLOC = """let Latest = toscalar(GenAIModelCost_CL | summarize arg_max(TimeGenerated, ScanId) | project ScanId);
let C = GenAIModelCost_CL
  | where ScanId == Latest and Grain == 'Daily'
  | where UsageDate >= $__timeFrom and UsageDate < $__timeTo
  | where MeterCategory in ('Foundry Models', 'SaaS', 'Cognitive Services')
  | extend Bucket = iff(MeterSubCategory startswith 'Claude', 'Claude', 'OpenAI');
let ClaudeCost = toscalar(C | where Bucket == 'Claude' | summarize sum(Cost));
let OpenAICost = toscalar(C | where Bucket == 'OpenAI' | summarize sum(Cost));
let ClaudeW = AzureDiagnostics
  | where Category == 'GatewayLogs' and TimeGenerated >= $__timeFrom and TimeGenerated < $__timeTo
  | where tostring(apiId_s) == 'anthropic-api' and tostring(url_s) has '/messages'
        and tostring(url_s) !has 'count_tokens'
  | summarize W = todouble(count()) by Product = tostring(productId_s), Consumer = tostring(apimSubscriptionId_s)
  | where isnotempty(Product);
let OpenAIW = AppMetrics
  | where TimeGenerated >= $__timeFrom and TimeGenerated < $__timeTo
  | where Name in ('Prompt Tokens', 'Completion Tokens')
  | extend P = todynamic(Properties)
  | extend Product = tostring(P['Product ID']), Consumer = tostring(P['Subscription ID'])
  | where isnotempty(Product)
  | summarize W = sum(Sum) by Product, Consumer;
let CT = toscalar(ClaudeW | summarize sum(W));
let OT = toscalar(OpenAIW | summarize sum(W));
let Alloc = union
    (ClaudeW | extend Cost = ClaudeCost * W / iff(CT == 0, 1.0, CT), Family = 'Claude'),
    (OpenAIW | extend Cost = OpenAICost * W / iff(OT == 0, 1.0, OT), Family = 'OpenAI and others');
"""



def q(query, fmt="time_series", ref="A"):
    return [{
        "refId": ref, "queryType": "Azure Log Analytics", "datasource": DS,
        "subscription": SUB, "subscriptions": [],
        "azureLogAnalytics": {"query": query, "resource": LAW, "resultFormat": fmt,
                              # queries that filter UsageDate themselves opt out of
                              # dashboardTime; the rest stay bound to the time picker
                              "dashboardTime": "$__timeFrom" not in query,
                              "timeColumn": "TimeGenerated"},
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


# Token volumes taken from BILLED QUANTITIES, so every model family is covered
# including Anthropic. Unit is inferred from price magnitude: Azure quotes some
# meters per 1K tokens and some per 1M, and the meter name does not reliably say
# which. The unit is derived from the meter NAME, not from price magnitude - a
# price-threshold rule breaks on genuinely cheap meters (cached input, nano
# models) whose real per-1M price is under 0.1 EUR. Verified: cache read lands
# at ~10% of input for every family, and output at ~5x input for Claude.
BILLED_TOKENS = """let Latest = toscalar(GenAIModelCost_CL | summarize arg_max(TimeGenerated, ScanId) | project ScanId);
GenAIModelCost_CL
| where ScanId == Latest and Grain == 'Monthly'
| where MeterCategory in ('Foundry Models', 'SaaS', 'Cognitive Services')
| where UsageQuantity > 0
| extend Unit = case(
    Meter has '1M Tokens',        1000000.0,   // OpenAI meters state the unit
    Meter has 'paygo-inference-', 1000.0,      // older Anthropic plans quote per 1K
    Meter has 'paygo-inf',        1000000.0,   // newer Anthropic plans quote per 1M
    1000.0)
| extend Tokens = UsageQuantity * Unit
| extend TokenType = case(
    Meter has 'cache-hit' or Meter has 'cchd' or Meter has 'cached' or Meter has ' cd ' or Meter has 'Cd Inp', 'Cache read',
    Meter has 'cache-write' or Meter has 'Cd Wr', 'Cache write',
    Meter has 'output' or Meter has ' opt ' or Meter has 'Outp' or Meter has 'outpt', 'Output',
    Meter has 'input' or Meter has ' inp ' or Meter has 'Inp', 'Input', 'Other')
| where TokenType != 'Other'
"""

panels = []

# ================= AT A GLANCE =================
panels.append(row("Consumption at a Glance", {"h": 1, "w": 24, "x": 0, "y": 0}))

panels.append(stat("Total Tokens (OpenAI family)", "Prompt and completion tokens from AppMetrics. Covers OpenAI, Kimi and embeddings ONLY - AppMetrics carries no Anthropic rows. For Anthropic volumes see Billed Token Volume by Model Family below.",
                   BASE + FILT + "| summarize Tokens=sum(Sum) by bin(TimeGenerated, 1h)\n| order by TimeGenerated asc",
                   "short", BLUE, {"h": 5, "w": 4, "x": 0, "y": 1}))

panels.append(stat("Prompt Tokens (OpenAI family)", "Input tokens from AppMetrics. Excludes Anthropic.",
                   BASE + FILT + "| where Name == 'Prompt Tokens'\n| summarize Tokens=sum(Sum) by bin(TimeGenerated, 1h)\n| order by TimeGenerated asc",
                   "short", BLUE, {"h": 5, "w": 4, "x": 4, "y": 1}))

panels.append(stat("Completion Tokens (OpenAI family)", "Generated tokens from AppMetrics. Excludes Anthropic. Priced several times higher than input.",
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

panels.append(stat("Active Models (OpenAI family)", "Distinct deployments in AppMetrics. Excludes Anthropic.",
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

panels.append(bar("Tokens by Model (OpenAI family)",
                  "Tokens per deployment from AppMetrics. Anthropic models are absent - see the billed-token panel for those.",
                  BASE + FILT + "| summarize Tokens=sum(Sum) by Model\n| top 15 by Tokens desc",
                  "short", {"h": 10, "w": 12, "x": 0, "y": 29}))


panels.append(bar(
    "Tokens by Model (all families, billed)",
    "Total billed token volume per model family, Anthropic included. Sourced from billed quantities, so this is the companion to the OpenAI-family chart on the left, which cannot show Claude. For Anthropic each family IS the model; for OpenAI, billing groups deployments into one family.",
    BILLED_TOKENS +
    "| summarize Tokens = sum(Tokens) by ['Model family'] = MeterSubCategory\n"
    "| order by Tokens desc",
    "short", {"h": 10, "w": 12, "x": 12, "y": 29}))

panels.append(ts("Input vs Output Tokens Over Time",
                 "Prompt against completion tokens. Divergence matters: output tokens are priced far higher, so a rising completion line raises cost faster than the volume implies.",
                 BASE + FILT +
                 "| summarize Prompt=sumif(Sum, Name=='Prompt Tokens'), Completion=sumif(Sum, Name=='Completion Tokens') by bin(TimeGenerated, 1h)\n"
                 "| order by TimeGenerated asc",
                 "short", {"h": 9, "w": 24, "x": 0, "y": 39}))
panels.append(table(
    "Billed Token Volume by Model Family (all models)",
    "Exact token volumes for EVERY model family including Anthropic, taken from billed quantities rather than logs. This is the only accurate source of Claude token counts - GatewayLlmLogs never populates completion or cached tokens. Monthly grain, so it does not follow fine time ranges.",
    BILLED_TOKENS +
    "| summarize Input=sum(iff(TokenType=='Input', Tokens, 0.0)),\n"
    "            Output=sum(iff(TokenType=='Output', Tokens, 0.0)),\n"
    "            ['Cache read']=sum(iff(TokenType=='Cache read', Tokens, 0.0)),\n"
    "            ['Cache write']=sum(iff(TokenType=='Cache write', Tokens, 0.0)),\n"
    "            ['Cost EUR']=round(sum(Cost), 2) by ['Model family']=MeterSubCategory\n"
    "| extend Total = Input + Output + ['Cache read'] + ['Cache write']\n"
    "| project ['Model family'], Total, Input, Output, ['Cache read'], ['Cache write'], ['Cost EUR']\n"
    "| order by ['Cost EUR'] desc",
    {"h": 12, "w": 24, "x": 0, "y": 38},
    [w("Model family", 260),
     grad("Total", BLUE, "short", 0, 120), grad("Input", BLUE, "short", 0, 110),
     grad("Output", BLUE, "short", 0, 110),
     grad("Cache read", [{"color": "green", "value": None}], "short", 0, 120),
     grad("Cache write", [{"color": "yellow", "value": None}], "short", 0, 120),
     grad("Cost EUR", GREEN, "currencyEUR", 2, 120)],
    sort_col="Cost EUR"))

panels.append(table("Model Consumption Detail (OpenAI family)",
                    "Per-deployment token split with consuming products and regions. Sourced from AppMetrics, which carries NO Anthropic rows - Claude models will not appear here. Accurate Anthropic volumes are in Billed Token Volume by Model Family.",
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
    text("How this cost is calculated", """
### Actual billed cost, allocated - not estimated

Totals come straight from Azure Cost Management via `GenAIModelCost_CL`, so
**the figures here reconcile to the real invoice**. Nothing is derived from a
price list.

Allocation across products uses the best complete signal for each family:

| Family | Allocated by | Why |
|---|---|---|
| Claude | share of `anthropic-api` requests | AppMetrics carries no Anthropic rows, and `GatewayLlmLogs` has `deploymentName_s` empty on ~64% of rows |
| OpenAI, Kimi, embeddings | share of tokens (AppMetrics) | complete for this family, and more precise than request counts |

### Read this before using it for chargeback

The **total is exact**. The **per-product split is an allocation**, not a
measurement — Claude cost is spread by request count, so a product sending long
Opus prompts and one sending short Haiku prompts are treated alike per request.
Directionally right, not invoice-grade per product.

Fixing that properly needs APIM to emit per-request token counts for Anthropic.
See SOP §5.3.
""", {"h": 10, "w": 7, "x": 0, "y": 50}),

    table("Actual Cost by Product",
          "Billed model spend allocated to each APIM product. Totals reconcile to the Azure invoice. Claude is included - unlike any token-derived estimate.",
          ALLOC + "Alloc\n"
          "| summarize ['Total EUR'] = round(sum(Cost), 2),\n"
          "            ['Claude EUR'] = round(sumif(Cost, Family == 'Claude'), 2),\n"
          "            ['OpenAI EUR'] = round(sumif(Cost, Family != 'Claude'), 2) by Product\n"
          "| order by ['Total EUR'] desc",
          {"h": 10, "w": 17, "x": 7, "y": 50},
          [w("Product", 420), grad("Total EUR", GREEN, "currencyEUR", 2, 130),
           grad("Claude EUR", BLUE, "currencyEUR", 2, 130),
           grad("OpenAI EUR", BLUE, "currencyEUR", 2, 130)],
          sort_col="Total EUR"),

    table("Actual Cost by Model Family",
          "Billed spend per model family, straight from Cost Management. These figures are exact - no allocation involved.",
          "let Latest = toscalar(GenAIModelCost_CL | summarize arg_max(TimeGenerated, ScanId) | project ScanId);\n"
          "GenAIModelCost_CL\n"
          "| where ScanId == Latest and Grain == 'Daily'\n"
          "| where UsageDate >= $__timeFrom and UsageDate < $__timeTo\n"
          "| where MeterCategory in ('Foundry Models', 'SaaS', 'Cognitive Services')\n"
          "| summarize ['Cost EUR'] = round(sum(Cost), 2) by ['Model family'] = MeterSubCategory\n"
          "| order by ['Cost EUR'] desc",
          {"h": 10, "w": 12, "x": 0, "y": 60},
          [w("Model family", 300), grad("Cost EUR", GREEN, "currencyEUR", 2, 140)],
          sort_col="Cost EUR"),

    table("Actual Cost by Consumer",
          "Billed model spend allocated one level below product, to the APIM subscription actually making the calls.",
          ALLOC + "Alloc\n"
          "| summarize ['Total EUR'] = round(sum(Cost), 2) by Consumer, Product\n"
          "| order by ['Total EUR'] desc",
          {"h": 10, "w": 12, "x": 12, "y": 60},
          [w("Consumer", 260), w("Product", 260),
           grad("Total EUR", GREEN, "currencyEUR", 2, 130)],
          sort_col="Total EUR"),
]

panels.append(row("Actual Cost (allocated from Azure billing)", {"h": 1, "w": 24, "x": 0, "y": 49},
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



def reflow(ps):
    """Assign gridPos top-down/left-right so panels cannot overlap.
    Rows span full width and reset the cursor; everything else packs by width."""
    y = 0
    x = 0
    row_h = 0
    for p in ps:
        g = p.setdefault("gridPos", {"h": 8, "w": 12, "x": 0, "y": 0})
        if p["type"] == "row":
            if x:
                y += row_h
                x = 0
                row_h = 0
            g.update({"h": 1, "w": 24, "x": 0, "y": y})
            y += 1
            continue
        if x + g["w"] > 24:
            y += row_h
            x = 0
            row_h = 0
        g["x"] = x
        g["y"] = y
        x += g["w"]
        row_h = max(row_h, g["h"])
    return ps


panels = reflow(panels)

dashboard = {
    "uid": "genai-token-chargeback",
    "title": "GenAI Hub - Token Economics and Chargeback",
    "description": ("Token consumption and cost chargeback for GenAI Hub. Cost is ACTUAL billed spend "
                    "from Azure Cost Management, allocated across products - Claude by request share, "
                    "OpenAI by token share - so totals reconcile to the invoice and Claude is included. "
                    "Token panels come from AppMetrics and cover OpenAI-family models only."),
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
print("written:", out)
