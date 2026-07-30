import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = os.path.join(_HERE, "..", "dashboards")

import json

SUB = "e4e9074e-0238-41e6-929e-edda76b67e79"
LAW = f"/subscriptions/{SUB}/resourceGroups/gaih-prd01-mon-rg/providers/Microsoft.OperationalInsights/workspaces/gaih-prd01-law0"
DS = {"type": "grafana-azure-monitor-datasource", "uid": "azure-monitor-oob"}

GW = "AzureDiagnostics | where ResourceProvider == 'MICROSOFT.APIMANAGEMENT' and Category == 'GatewayLogs'"
LLM = "AzureDiagnostics | where Category == 'GatewayLlmLogs'"
DEP = "| extend Dep = extract(@'/deployments/([^/?]+)', 1, tostring(url_s))"
FILT = ("| where isnotempty(Dep)\n"
        "| where '*' in (${deployment:singlequote}) or Dep in (${deployment:singlequote})\n"
        "| where '*' in (${consumer:singlequote}) or tostring(apimSubscriptionId_s) in (${consumer:singlequote})")


def q(query, fmt="time_series", ref="A"):
    return [{
        "refId": ref,
        "queryType": "Azure Log Analytics",
        "datasource": DS,
        "subscription": SUB,
        "subscriptions": [],
        "azureLogAnalytics": {"query": query, "resource": LAW, "resultFormat": fmt,
                              "dashboardTime": True, "timeColumn": "TimeGenerated"},
    }]


def stat(title, desc, query, unit, steps, gp, calc="lastNotNull",
         color_mode="value", graph="area", decimals=None):
    return {
        "type": "stat", "title": title, "description": desc,
        "datasource": DS, "gridPos": gp, "targets": q(query),
        "fieldConfig": {"defaults": {
            "unit": unit, "decimals": decimals,
            "color": {"mode": "thresholds"},
            "thresholds": {"mode": "absolute", "steps": steps},
            "mappings": [],
        }, "overrides": []},
        "options": {
            "colorMode": color_mode, "graphMode": graph, "justifyMode": "auto",
            "orientation": "auto", "textMode": "auto", "wideLayout": True,
            "showPercentChange": False,
            "reduceOptions": {"calcs": [calc], "fields": "", "values": False},
        },
    }


def ts(title, desc, query, unit, gp, fill=18, stack=None, width=2, points=False):
    custom = {
        "drawStyle": "line", "lineInterpolation": "smooth", "lineWidth": width,
        "fillOpacity": fill, "gradientMode": "opacity", "showPoints": "never",
        "pointSize": 5, "spanNulls": True, "axisSoftMin": 0,
        "scaleDistribution": {"type": "linear"},
        "hideFrom": {"legend": False, "tooltip": False, "viz": False},
    }
    if stack:
        custom["stacking"] = {"mode": stack, "group": "A"}
        custom["fillOpacity"] = 65
        custom["lineWidth"] = 1
    return {
        "type": "timeseries", "title": title, "description": desc,
        "datasource": DS, "gridPos": gp, "targets": q(query),
        "fieldConfig": {"defaults": {
            "unit": unit, "color": {"mode": "palette-classic"},
            "custom": custom,
            "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
        }, "overrides": []},
        "options": {
            "legend": {"displayMode": "table", "placement": "bottom",
                       "showLegend": True, "calcs": ["mean", "max"]},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
    }


def table(title, desc, query, gp, overrides):
    return {
        "type": "table", "title": title, "description": desc,
        "datasource": DS, "gridPos": gp, "targets": q(query, "table"),
        "fieldConfig": {"defaults": {
            "custom": {"align": "auto", "cellOptions": {"type": "auto"},
                       "inspect": False, "filterable": True},
            "color": {"mode": "thresholds"},
            "thresholds": {"mode": "absolute", "steps": [{"color": "text", "value": None}]},
        }, "overrides": overrides},
        "options": {"showHeader": True, "footer": {"show": False, "reducer": ["sum"], "countRows": False},
                    "cellHeight": "sm",
                    "sortBy": [{"displayName": "Calls", "desc": True}]},
    }


def row(title, gp, collapsed=False, panels=None):
    return {"type": "row", "title": title, "gridPos": gp,
            "collapsed": collapsed, "panels": panels or []}


def gauge_override(field, steps, unit="percent", decimals=2):
    return {
        "matcher": {"id": "byName", "options": field},
        "properties": [
            {"id": "unit", "value": unit},
            {"id": "decimals", "value": decimals},
            {"id": "custom.cellOptions",
             "value": {"type": "gauge", "mode": "gradient", "valueDisplayMode": "text"}},
            {"id": "thresholds", "value": {"mode": "absolute", "steps": steps}},
            {"id": "max", "value": 100}, {"id": "min", "value": 0},
        ],
    }


def color_bg(field, steps, unit="short", decimals=0):
    return {
        "matcher": {"id": "byName", "options": field},
        "properties": [
            {"id": "unit", "value": unit},
            {"id": "decimals", "value": decimals},
            {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "gradient"}},
            {"id": "thresholds", "value": {"mode": "absolute", "steps": steps}},
        ],
    }


# ---------- threshold vocabularies ----------
AVAIL = [{"color": "red", "value": None}, {"color": "orange", "value": 99},
         {"color": "yellow", "value": 99.5}, {"color": "green", "value": 99.9}]
ERRPCT = [{"color": "green", "value": None}, {"color": "yellow", "value": 1},
          {"color": "orange", "value": 5}, {"color": "red", "value": 10}]
LAT = [{"color": "green", "value": None}, {"color": "yellow", "value": 5000},
       {"color": "orange", "value": 15000}, {"color": "red", "value": 30000}]
NEUTRAL = [{"color": "blue", "value": None}]
BROKEN = [{"color": "green", "value": None}, {"color": "red", "value": 1}]

panels = []

# ================= KPI ROW =================
panels.append(row("Service Health at a Glance", {"h": 1, "w": 24, "x": 0, "y": 0}))

panels.append(stat(
    "Gateway Availability", "Share of gateway calls not returning 5xx, over the selected window. Green at or above 99.9%.",
    f"{GW} {DEP} {FILT}\n| summarize Total=count(), Bad=countif(responseCode_d >= 500) by bin(TimeGenerated, 5m)\n| project TimeGenerated, Availability = 100.0 * (Total - Bad) / Total\n| order by TimeGenerated asc",
    "percent", AVAIL, {"h": 5, "w": 4, "x": 0, "y": 1}, calc="mean", decimals=3))

panels.append(stat(
    "Requests", "Total gateway calls in the selected window.",
    f"{GW} {DEP} {FILT}\n| summarize Requests=count() by bin(TimeGenerated, 5m)\n| order by TimeGenerated asc",
    "short", NEUTRAL, {"h": 5, "w": 4, "x": 4, "y": 1}, calc="sum"))

panels.append(stat(
    "Client Error Rate", "Percentage of calls returning 4xx or 5xx. Includes gateway-side rejections.",
    f"{GW} {DEP} {FILT}\n| summarize Total=count(), Bad=countif(responseCode_d >= 400) by bin(TimeGenerated, 5m)\n| project TimeGenerated, ErrorRate = 100.0 * Bad / Total\n| order by TimeGenerated asc",
    "percent", ERRPCT, {"h": 5, "w": 4, "x": 8, "y": 1}, calc="mean", decimals=2))

panels.append(stat(
    "P95 Latency", "95th percentile end-to-end gateway duration, averaged across buckets.",
    f"{GW} {DEP} {FILT}\n| summarize P95=percentile(DurationMs, 95) by bin(TimeGenerated, 5m)\n| order by TimeGenerated asc",
    "ms", LAT, {"h": 5, "w": 4, "x": 12, "y": 1}, calc="mean", decimals=0))

panels.append(stat(
    "Tokens Processed", "Total LLM tokens billed through the gateway (GatewayLlmLogs). Only providers that emit LLM logs are counted.",
    f"{LLM}\n| where '*' in (${{deployment:singlequote}}) or tostring(deploymentName_s) in (${{deployment:singlequote}})\n| summarize Tokens=sum(totalTokens_d) by bin(TimeGenerated, 5m)\n| order by TimeGenerated asc",
    "short", NEUTRAL, {"h": 5, "w": 4, "x": 16, "y": 1}, calc="sum"))

panels.append(stat(
    "Failing Deployments", "Deployments where more than 90% of calls fail. Any value above zero means a model route is effectively down.",
    f"{GW} {DEP} {FILT}\n| summarize Total=count(), Bad=countif(responseCode_d >= 400) by Dep\n| where Total >= 20 and (100.0 * Bad / Total) > 90\n| summarize Broken=count()",
    "short", BROKEN, {"h": 5, "w": 4, "x": 20, "y": 1},
    color_mode="background_solid", graph="none"))

# ================= HEALTH MATRIX =================
panels.append(row("Deployment Health Matrix", {"h": 1, "w": 24, "x": 0, "y": 6}))

panels.append(table(
    "Model Deployment Health",
    "Per-deployment traffic, reliability and latency. Sorted by call volume. Error Rate is colour-graded; anything at 100% is a fully broken route.",
    f"{GW} {DEP} {FILT}\n"
    "| summarize Calls=count(), Errors=countif(responseCode_d >= 400), "
    "ServerErrors=countif(responseCode_d >= 500), "
    "P50=round(percentile(DurationMs, 50)), P95=round(percentile(DurationMs, 95)) by Dep\n"
    "| extend ErrorRate = round(100.0 * Errors / Calls, 2), "
    "Availability = round(100.0 * (Calls - ServerErrors) / Calls, 3)\n"
    "| project Deployment=Dep, Calls, ErrorRate, Availability, P50, P95, Errors\n"
    "| order by Calls desc",
    {"h": 12, "w": 24, "x": 0, "y": 7},
    [
        color_bg("ErrorRate", ERRPCT, "percent", 2),
        gauge_override("Availability", AVAIL),
        color_bg("P95", LAT, "ms", 0),
        color_bg("P50", LAT, "ms", 0),
        {"matcher": {"id": "byName", "options": "Deployment"},
         "properties": [{"id": "custom.width", "value": 340}]},
    ]))

# ================= TRAFFIC & RELIABILITY =================
panels.append(row("Traffic and Reliability", {"h": 1, "w": 24, "x": 0, "y": 19}))

panels.append(ts(
    "Response Classes", "Gateway responses grouped by HTTP status class, stacked to show composition of traffic.",
    f"{GW} {DEP} {FILT}\n"
    "| extend Code = toint(responseCode_d)\n"
    "| extend Class = case(Code >= 500, '5xx server', Code >= 400, '4xx client', "
    "Code >= 300, '3xx redirect', Code >= 200, '2xx success', 'other')\n"
    "| summarize Requests=count() by bin(TimeGenerated, 5m), Class\n| order by TimeGenerated asc",
    "short", {"h": 9, "w": 12, "x": 0, "y": 20}, stack="normal"))

panels.append(ts(
    "Latency Percentiles", "P50, P95 and P99 end-to-end gateway duration. Divergence between P50 and P99 indicates tail-latency problems.",
    f"{GW} {DEP} {FILT}\n"
    "| summarize P50=percentile(DurationMs, 50), P95=percentile(DurationMs, 95), "
    "P99=percentile(DurationMs, 99) by bin(TimeGenerated, 5m)\n| order by TimeGenerated asc",
    "ms", {"h": 9, "w": 12, "x": 12, "y": 20}))

panels.append(ts(
    "Throttling (429)", "Rate-limited calls. Sustained 429s mean consumers are exceeding their quota or backend capacity is short.",
    f"{GW} {DEP} {FILT}\n| where responseCode_d == 429\n"
    "| summarize Throttled=count() by bin(TimeGenerated, 5m), Consumer=tostring(apimSubscriptionId_s)\n"
    "| order by TimeGenerated asc",
    "short", {"h": 8, "w": 12, "x": 0, "y": 29}, stack="normal"))

panels.append(ts(
    "Backend vs Gateway Time", "Average time spent in the model backend compared with total gateway duration. A widening gap points at gateway-side overhead.",
    f"{GW} {DEP} {FILT}\n"
    "| summarize ['Backend time']=avg(backendTime_d), ['Total gateway time']=avg(DurationMs) "
    "by bin(TimeGenerated, 5m)\n| order by TimeGenerated asc",
    "ms", {"h": 8, "w": 12, "x": 12, "y": 29}))

# ================= TOKEN ECONOMICS (collapsed) =================
token_panels = [
    ts("Token Throughput by Deployment",
       "Total tokens per interval, split by model deployment. Sourced from GatewayLlmLogs.",
       f"{LLM}\n| where '*' in (${{deployment:singlequote}}) or tostring(deploymentName_s) in (${{deployment:singlequote}})\n"
       "| summarize Tokens=sum(totalTokens_d) by bin(TimeGenerated, 5m), Deployment=tostring(deploymentName_s)\n"
       "| order by TimeGenerated asc",
       "short", {"h": 9, "w": 12, "x": 0, "y": 39}, stack="normal"),

    ts("Prompt vs Completion Tokens",
       "Split of input against generated tokens. A rising completion share usually means longer answers and higher cost per call.",
       f"{LLM}\n| where '*' in (${{deployment:singlequote}}) or tostring(deploymentName_s) in (${{deployment:singlequote}})\n"
       "| summarize Prompt=sum(promptTokens_d), Completion=sum(completionTokens_d), "
       "Cached=sum(promptCachedTokens_d), Reasoning=sum(completionReasoningTokens_d) "
       "by bin(TimeGenerated, 5m)\n| order by TimeGenerated asc",
       "short", {"h": 9, "w": 12, "x": 12, "y": 39}),

    table("Token Economics by Deployment",
          "Per-deployment token totals with prompt-cache hit rate and streaming adoption. Cache hit rate above zero directly reduces spend.",
          f"{LLM}\n| where '*' in (${{deployment:singlequote}}) or tostring(deploymentName_s) in (${{deployment:singlequote}})\n"
          "| summarize Calls=count(), Total=sum(totalTokens_d), Prompt=sum(promptTokens_d), "
          "Completion=sum(completionTokens_d), Cached=sum(promptCachedTokens_d), "
          "Reasoning=sum(completionReasoningTokens_d), Streamed=countif(isStreamCompletion_b == true) "
          "by Deployment=tostring(deploymentName_s)\n"
          "| extend ['Cache hit %'] = round(100.0 * Cached / iff(Prompt == 0, 1.0, Prompt), 2), "
          "['Streaming %'] = round(100.0 * Streamed / Calls, 1), "
          "['Tokens per call'] = round(Total / Calls)\n"
          "| project Deployment, Calls, Total, ['Tokens per call'], Prompt, Completion, "
          "Reasoning, ['Cache hit %'], ['Streaming %']\n| order by Total desc",
          {"h": 11, "w": 24, "x": 0, "y": 48},
          [
              color_bg("Total", NEUTRAL, "short", 0),
              gauge_override("Cache hit %",
                             [{"color": "red", "value": None}, {"color": "orange", "value": 5},
                              {"color": "yellow", "value": 20}, {"color": "green", "value": 40}]),
              gauge_override("Streaming %", [{"color": "blue", "value": None}], decimals=1),
              {"matcher": {"id": "byName", "options": "Deployment"},
               "properties": [{"id": "custom.width", "value": 340}]},
          ]),
]
panels.append(row("Token Economics", {"h": 1, "w": 24, "x": 0, "y": 37},
                  collapsed=True, panels=token_panels))

# ================= CONSUMERS (collapsed) =================
consumer_panels = [
    table("Consumer Health",
          "Traffic and reliability per APIM subscription. Use this to tell platform-wide incidents apart from a single misbehaving consumer.",
          f"{GW} {DEP} {FILT}\n"
          "| summarize Calls=count(), Errors=countif(responseCode_d >= 400), "
          "Throttled=countif(responseCode_d == 429), P95=round(percentile(DurationMs, 95)) "
          "by Consumer=tostring(apimSubscriptionId_s), Product=tostring(productId_s)\n"
          "| extend ['Error %'] = round(100.0 * Errors / Calls, 2)\n"
          "| project Consumer, Product, Calls, ['Error %'], Throttled, P95\n| order by Calls desc",
          {"h": 11, "w": 24, "x": 0, "y": 39},
          [
              color_bg("Error %", ERRPCT, "percent", 2),
              color_bg("Throttled", [{"color": "green", "value": None}, {"color": "orange", "value": 1}], "short", 0),
              color_bg("P95", LAT, "ms", 0),
              {"matcher": {"id": "byName", "options": "Consumer"},
               "properties": [{"id": "custom.width", "value": 320}]},
          ]),

    table("Gateway Rejection Reasons",
          "Calls the gateway rejected before reaching a model backend. A blank backend code with a 4xx means the request never left APIM, usually a routing or policy fault.",
          f"{GW} {DEP} {FILT}\n"
          "| where responseCode_d >= 400\n"
          "| extend BackendCode = toint(coalesce(backendResponseCode_d, real(0)))\n"
          "| summarize Calls=count() by Deployment=Dep, ResponseCode=toint(responseCode_d), "
          "BackendCode, Reason=tostring(column_ifexists('lastError_reason_s', 'not recorded'))\n"
          "| order by Calls desc | take 30",
          {"h": 11, "w": 24, "x": 0, "y": 50},
          [color_bg("Calls", [{"color": "yellow", "value": None}, {"color": "red", "value": 500}], "short", 0)]),
]
panels.append(row("Consumers and Rejections", {"h": 1, "w": 24, "x": 0, "y": 38},
                  collapsed=True, panels=consumer_panels))


def var(name, label, query, desc):
    return {
        "name": name, "label": label, "description": desc,
        "type": "query", "datasource": DS,
        "query": {
            "queryType": "Azure Log Analytics",
            "azureLogAnalytics": {"query": query, "resource": LAW},
            "subscription": SUB,
        },
        "refresh": 1, "multi": True, "includeAll": True, "allValue": "'*'",
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
        "options": [], "sort": 1, "hide": 0,
    }


dashboard = {
    "uid": "genai-model-operations",
    "title": "GenAI Hub - Model Operations",
    "description": "Operational command centre for the GenAI Hub model gateway. Deployment-level reliability, latency and token economics, filterable by deployment and consumer.",
    "tags": ["genai-hub", "production", "operations", "model-gateway"],
    "timezone": "browser",
    "editable": True,
    "graphTooltip": 1,
    "refresh": "5m",
    "schemaVersion": 39,
    "time": {"from": "now-24h", "to": "now"},
    "timepicker": {"refresh_intervals": ["1m", "5m", "15m", "30m", "1h", "6h"]},
    "templating": {"list": [
        var("deployment", "Model deployment",
            f"{GW} {DEP}\n| where isnotempty(Dep)\n| distinct Dep\n| order by Dep asc",
            "Filter every panel to one or more model deployments."),
        var("consumer", "Consumer",
            f"{GW}\n| distinct Consumer=tostring(apimSubscriptionId_s)\n| where isnotempty(Consumer)\n| order by Consumer asc",
            "Filter to specific APIM subscriptions (consuming applications)."),
    ]},
    "links": [
        {"title": "GenAI Hub dashboards", "type": "dashboards", "tags": ["genai-hub"],
         "asDropdown": True, "icon": "external link", "includeVars": False,
         "keepTime": True, "targetBlank": False, "tooltip": "", "url": ""},
    ],
    "panels": panels,
}

out = os.path.join(_OUT, "genai-model-operations.json")
with open(out, "w") as f:
    json.dump(dashboard, f, indent=2)

flat = []
for p in panels:
    flat.append(p)
    flat.extend(p.get("panels", []))
print("panels:", len(flat), "| rows:", sum(1 for p in flat if p["type"] == "row"))
print("vars:", [v["name"] for v in dashboard["templating"]["list"]])
print("written:", out)
