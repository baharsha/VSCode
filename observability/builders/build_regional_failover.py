import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = os.path.join(_HERE, "..", "dashboards")

import json

SUB = "e4e9074e-0238-41e6-929e-edda76b67e79"
LAW = (f"/subscriptions/{SUB}/resourceGroups/gaih-prd01-mon-rg/providers/"
       "Microsoft.OperationalInsights/workspaces/gaih-prd01-law0")
DS = {"type": "grafana-azure-monitor-datasource", "uid": "azure-monitor-oob"}

# Region tiers confirmed by the platform owner:
#   Sweden Central = Primary, East US 2 = Secondary, West Europe = Tertiary
GW = ("AzureDiagnostics\n"
      "| where ResourceProvider == 'MICROSOFT.APIMANAGEMENT' and Category == 'GatewayLogs'\n"
      "| extend BU = tostring(backendUrl_s), Dep = extract(@'/deployments/([^/?]+)', 1, tostring(url_s))\n"
      "| where isnotempty(BU)\n"
      "| extend Region = case(BU has '-swc-' or BU has 'swedencentral', 'Sweden Central',\n"
      "                       BU has '-eus2-' or BU has 'eastus2',      'East US 2',\n"
      "                       BU has '-euw-'  or BU has 'westeurope',   'West Europe',\n"
      "                       'Other')\n"
      "| extend Tier = case(Region == 'Sweden Central', '1 Primary',\n"
      "                     Region == 'East US 2',      '2 Secondary',\n"
      "                     Region == 'West Europe',    '3 Tertiary', '4 Unclassified')\n"
      "| extend OnFailover = Tier in ('2 Secondary', '3 Tertiary')\n")

FILT = ("| where '*' in (${deployment:singlequote}) or Dep in (${deployment:singlequote})\n")


def q(query, fmt="time_series", ref="A"):
    return [{"refId": ref, "queryType": "Azure Log Analytics", "datasource": DS,
             "subscription": SUB, "subscriptions": [],
             "azureLogAnalytics": {"query": query, "resource": LAW, "resultFormat": fmt,
                                   "dashboardTime": True, "timeColumn": "TimeGenerated"}}]


def stat(title, desc, query, unit, steps, gp, calc="sum", graph="area",
         color_mode="value", decimals=None):
    return {"type": "stat", "title": title, "description": desc, "datasource": DS,
            "gridPos": gp, "targets": q(query),
            "fieldConfig": {"defaults": {
                "unit": unit, "decimals": decimals, "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": steps}, "mappings": []},
                "overrides": []},
            "options": {"colorMode": color_mode, "graphMode": graph, "justifyMode": "auto",
                        "orientation": "auto", "textMode": "auto", "wideLayout": True,
                        "showPercentChange": False,
                        "reduceOptions": {"calcs": [calc], "fields": "", "values": False}}}


REGION_COLORS = [
    ("Sweden Central", "green"), ("East US 2", "orange"), ("West Europe", "purple"),
    ("Other", "red"),
    ("1 Primary", "green"), ("2 Secondary", "orange"), ("3 Tertiary", "purple"),
]


def region_overrides():
    return [{"matcher": {"id": "byName", "options": n},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}
            for n, c in REGION_COLORS]


def ts(title, desc, query, unit, gp, stack=None, extra_over=None, fill=25):
    custom = {"drawStyle": "line", "lineInterpolation": "smooth", "lineWidth": 2,
              "fillOpacity": fill, "gradientMode": "opacity", "showPoints": "never",
              "spanNulls": True, "axisSoftMin": 0,
              "scaleDistribution": {"type": "linear"},
              "hideFrom": {"legend": False, "tooltip": False, "viz": False}}
    if stack:
        custom.update({"stacking": {"mode": stack, "group": "A"},
                       "fillOpacity": 75, "lineWidth": 1})
    return {"type": "timeseries", "title": title, "description": desc, "datasource": DS,
            "gridPos": gp, "targets": q(query),
            "fieldConfig": {"defaults": {
                "unit": unit, "color": {"mode": "palette-classic"}, "custom": custom,
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]}},
                "overrides": region_overrides() + (extra_over or [])},
            "options": {"legend": {"displayMode": "table", "placement": "bottom",
                                   "showLegend": True, "calcs": ["mean", "max"]},
                        "tooltip": {"mode": "multi", "sort": "desc"}}}


def table(title, desc, query, gp, overrides, sort_col=None):
    opts = {"showHeader": True, "cellHeight": "sm",
            "footer": {"show": False, "reducer": ["sum"], "countRows": False}}
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


def text(title, content, gp):
    return {"type": "text", "title": title, "gridPos": gp,
            "options": {"mode": "markdown", "content": content}}


def row(title, gp, collapsed=False, panels=None):
    return {"type": "row", "title": title, "gridPos": gp,
            "collapsed": collapsed, "panels": panels or []}


def grad(field, steps, unit="short", decimals=0, w=None):
    p = [{"id": "unit", "value": unit}, {"id": "decimals", "value": decimals},
         {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "gradient"}},
         {"id": "thresholds", "value": {"mode": "absolute", "steps": steps}}]
    if w:
        p.append({"id": "custom.width", "value": w})
    return {"matcher": {"id": "byName", "options": field}, "properties": p}


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


PRIMARY_OK = [{"color": "red", "value": None}, {"color": "orange", "value": 50},
              {"color": "yellow", "value": 75}, {"color": "green", "value": 90}]
FAILOVER = [{"color": "green", "value": None}, {"color": "yellow", "value": 5},
            {"color": "orange", "value": 25}, {"color": "red", "value": 50}]
ERRPCT = [{"color": "green", "value": None}, {"color": "yellow", "value": 1},
          {"color": "orange", "value": 5}, {"color": "red", "value": 10}]
LAT = [{"color": "green", "value": None}, {"color": "yellow", "value": 5000},
       {"color": "orange", "value": 15000}, {"color": "red", "value": 30000}]
NEUTRAL = [{"color": "blue", "value": None}]
THROTTLE = [{"color": "green", "value": None}, {"color": "orange", "value": 1}]


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

# ================= ROUTING AT A GLANCE =================
panels.append(row("Routing at a Glance", {"h": 1, "w": 24, "x": 0, "y": 0}))

panels.append(stat(
    "Served by Primary", "Share of model calls served by Sweden Central, the primary region. Anything well below 100% means the failover policy is actively diverting traffic.",
    GW + FILT + "| summarize Total=count(), Prim=countif(Tier == '1 Primary') by bin(TimeGenerated, 15m)\n"
    "| project TimeGenerated, PrimaryShare = 100.0 * Prim / Total\n| order by TimeGenerated asc",
    "percent", PRIMARY_OK, {"h": 5, "w": 4, "x": 0, "y": 1}, calc="mean", decimals=2))

panels.append(stat(
    "On Failover", "Share of calls served by a non-primary region (East US 2 or West Europe). This is the headline 'was it routed' number.",
    GW + FILT + "| summarize Total=count(), Fo=countif(OnFailover) by bin(TimeGenerated, 15m)\n"
    "| project TimeGenerated, FailoverShare = 100.0 * Fo / Total\n| order by TimeGenerated asc",
    "percent", FAILOVER, {"h": 5, "w": 4, "x": 4, "y": 1}, calc="mean", decimals=2))

panels.append(stat(
    "Secondary - East US 2", "Calls served by the secondary region.",
    GW + FILT + "| where Tier == '2 Secondary'\n| summarize Calls=count() by bin(TimeGenerated, 15m)\n| order by TimeGenerated asc",
    "short", NEUTRAL, {"h": 5, "w": 4, "x": 8, "y": 1}))

panels.append(stat(
    "Tertiary - West Europe", "Calls served by the tertiary region. Traffic here means both Sweden Central and East US 2 were unavailable or throttled.",
    GW + FILT + "| where Tier == '3 Tertiary'\n| summarize Calls=count() by bin(TimeGenerated, 15m)\n| order by TimeGenerated asc",
    "short", THROTTLE, {"h": 5, "w": 4, "x": 12, "y": 1}))

panels.append(stat(
    "Deployments Failing Over", "Model deployments with more than 10% of their traffic on a non-primary region in this window.",
    GW + FILT + "| summarize Total=count(), Fo=countif(OnFailover) by Dep\n"
    "| where Total >= 20 and (100.0 * Fo / Total) > 10\n| summarize Deployments=count()",
    "short", [{"color": "green", "value": None}, {"color": "orange", "value": 1}],
    {"h": 5, "w": 4, "x": 16, "y": 1}, calc="lastNotNull", graph="none",
    color_mode="background_solid"))

panels.append(stat(
    "Throttle Events (429)", "Rate-limit responses. These are what mark a route isThrottling and trigger the retry onto the next region.",
    GW + FILT + "| where responseCode_d == 429\n| summarize Throttled=count() by bin(TimeGenerated, 15m)\n| order by TimeGenerated asc",
    "short", THROTTLE, {"h": 5, "w": 4, "x": 20, "y": 1}))

# ================= WHERE TRAFFIC IS SERVED =================
panels.append(row("Where Traffic Is Being Served", {"h": 1, "w": 24, "x": 0, "y": 6}))

panels.append(ts(
    "Traffic by Region", "Calls per region over time, stacked. Green is the primary; orange and purple are failover. Widening colour bands show the policy shifting load.",
    GW + FILT + "| summarize Calls=count() by bin(TimeGenerated, 15m), Region\n| order by TimeGenerated asc",
    "short", {"h": 10, "w": 14, "x": 0, "y": 7}, stack="normal"))

panels.append(ts(
    "Failover Percentage", "Percentage of traffic on non-primary regions over time. Read this together with the trigger panel below - the policy caches a throttled route for up to an hour, so failover persists long after the error that caused it.",
    GW + FILT + "| summarize Total=count(), Fo=countif(OnFailover) by bin(TimeGenerated, 15m)\n"
    "| project TimeGenerated, ['Failover %'] = 100.0 * Fo / Total\n| order by TimeGenerated asc",
    "percent", {"h": 10, "w": 10, "x": 14, "y": 7},
    extra_over=[{"matcher": {"id": "byName", "options": "Failover %"},
                 "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}},
                                {"id": "custom.fillOpacity", "value": 30}]}]))

panels.append(table(
    "Region Health Comparison",
    "Reliability and latency per region. Worth checking whether the primary is genuinely the best place to serve traffic - if a failover region is faster and more reliable, the routing priority deserves review.",
    GW + FILT +
    "| summarize Calls=count(), Errors=countif(responseCode_d >= 400),\n"
    "            ServerErrors=countif(responseCode_d >= 500), Throttled=countif(responseCode_d == 429),\n"
    "            P50=round(percentile(DurationMs, 50)), P95=round(percentile(DurationMs, 95)),\n"
    "            Deployments=dcount(Dep) by Tier, Region\n"
    "| extend ['Error %'] = round(100.0 * Errors / Calls, 2),\n"
    "         ['Share %'] = round(100.0 * Calls / toscalar(\n"
    "             AzureDiagnostics | where ResourceProvider == 'MICROSOFT.APIMANAGEMENT'\n"
    "             and Category == 'GatewayLogs' and isnotempty(tostring(backendUrl_s)) | count), 2)\n"
    "| project Tier, Region, Calls, ['Share %'], ['Error %'], Throttled, P50, P95, Deployments\n"
    "| order by Tier asc",
    {"h": 8, "w": 24, "x": 0, "y": 17},
    [w("Region", 160), w("Tier", 120), grad("Calls", NEUTRAL, "short", 0, 120),
     gaugecell("Share %", NEUTRAL), gaugecell("Error %", ERRPCT, mx=15),
     grad("P50", LAT, "ms", 0, 100), grad("P95", LAT, "ms", 0, 100),
     grad("Throttled", THROTTLE, "short", 0, 110)]))

# ================= PER-DEPLOYMENT ROUTING =================
panels.append(row("Per-Deployment Routing", {"h": 1, "w": 24, "x": 0, "y": 25}))

panels.append(table(
    "Deployment Routing Matrix",
    "Where each model deployment was actually served. Failover % is the direct answer to 'was it routed'. A deployment at 0% never left the primary; one near 100% is effectively running from a backup region.",
    GW + FILT +
    "| summarize Calls=count(),\n"
    "            Primary=countif(Tier == '1 Primary'),\n"
    "            ['East US 2']=countif(Tier == '2 Secondary'),\n"
    "            ['West Europe']=countif(Tier == '3 Tertiary'),\n"
    "            Errors=countif(responseCode_d >= 400),\n"
    "            P95=round(percentile(DurationMs, 95)) by Deployment=Dep\n"
    "| where isnotempty(Deployment)\n"
    "| extend ['Failover %'] = round(100.0 * (['East US 2'] + ['West Europe']) / Calls, 2),\n"
    "         ['Error %'] = round(100.0 * Errors / Calls, 2)\n"
    "| extend Routing = case(['Failover %'] == 0, 'Primary only',\n"
    "                        ['Failover %'] >= 90, 'Failover only',\n"
    "                        ['Failover %'] >= 10, 'Split', 'Mostly primary')\n"
    "| project Deployment, Calls, Routing, ['Failover %'], Primary, ['East US 2'], ['West Europe'], ['Error %'], P95\n"
    "| order by Calls desc",
    {"h": 13, "w": 24, "x": 0, "y": 26},
    [dlink("Deployment", "Gateway health for this deployment", "genai-model-operations", "genai-hub-model-operations", "deployment", width=330),
     grad("Calls", NEUTRAL, "short", 0, 110),
     gaugecell("Failover %", FAILOVER),
     grad("East US 2", [{"color": "orange", "value": None}], "short", 0, 110),
     grad("West Europe", [{"color": "purple", "value": None}], "short", 0, 120),
     gaugecell("Error %", ERRPCT, mx=15), grad("P95", LAT, "ms", 0, 100),
     {"matcher": {"id": "byName", "options": "Routing"}, "properties": [
         {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
         {"id": "mappings", "value": [{"type": "value", "options": {
             "Primary only": {"color": "green", "index": 0},
             "Mostly primary": {"color": "yellow", "index": 1},
             "Split": {"color": "orange", "index": 2},
             "Failover only": {"color": "red", "index": 3}}}]},
         {"id": "custom.width", "value": 130}]}],
    sort_col="Calls"))

# ================= TRIGGERS (collapsed) =================
trigger_panels = [
    text("How failover actually works here", """
### Policy behaviour

`frag-backend-routing` wraps the call in `<retry count="3">`, firing when the backend returns **429** or **5xx** and at least one alternate route is free.

Route order is by `priority`, lowest first:

| Tier | Region |
|---|---|
| Primary | Sweden Central |
| Secondary | East US 2 |
| Tertiary | West Europe |

### Why triggers and failover do not line up in time

When a route fails, the policy marks it `isThrottling` with a `retryAfter`, then **caches that for up to 3600s**. Every later request skips the parked route until the timer clears.

So a single throttle at 23:00 can keep traffic on the secondary region for the next hour with **no further errors logged**. Do not expect the trigger chart and the failover chart to line up - compare them, do not correlate them minute by minute.

### One more caveat

APIM writes **one** GatewayLogs record per client request, showing the **final** backend. Retries inside a request are not logged separately, so these panels show where requests *ended up*, not how many attempts it took.
""", {"h": 11, "w": 7, "x": 0, "y": 40}),

    ts("Failover Triggers - 429 and 5xx by Region",
       "The errors that mark a route as throttled. Compare shape with the failover chart above, remembering the cache means effect lags cause by up to an hour.",
       GW + FILT +
       "| where responseCode_d == 429 or responseCode_d >= 500\n"
       "| extend Kind = strcat(Region, iff(responseCode_d == 429, ' 429', ' 5xx'))\n"
       "| summarize Events=count() by bin(TimeGenerated, 15m), Kind\n| order by TimeGenerated asc",
       "short", {"h": 11, "w": 17, "x": 7, "y": 40}, stack="normal"),

    ts("Latency by Region",
       "P95 gateway duration per region. Shows the real latency cost - or benefit - of being routed away from the primary.",
       GW + FILT + "| summarize P95=percentile(DurationMs, 95) by bin(TimeGenerated, 15m), Region\n| order by TimeGenerated asc",
       "ms", {"h": 9, "w": 12, "x": 0, "y": 51}),

    table("Backend Route Detail",
          "Traffic per configured APIM backend, mapped to its region and tier. Use this to confirm each model's routes resolve to the backends you expect.",
          GW + FILT +
          "| summarize Calls=count(), Errors=countif(responseCode_d >= 400),\n"
          "            P95=round(percentile(DurationMs, 95)), Deployments=dcount(Dep)\n"
          "            by Backend=tostring(backendId_s), Region, Tier\n"
          "| extend ['Error %'] = round(100.0 * Errors / Calls, 2)\n"
          "| project Backend, Region, Tier, Calls, ['Error %'], P95, Deployments\n"
          "| order by Calls desc",
          {"h": 9, "w": 12, "x": 12, "y": 51},
          [w("Backend", 240), grad("Calls", NEUTRAL, "short", 0, 110),
           gaugecell("Error %", ERRPCT, mx=15), grad("P95", LAT, "ms", 0, 100)],
          sort_col="Calls"),
]
panels.append(row("Failover Triggers and Region Health", {"h": 1, "w": 24, "x": 0, "y": 39},
                  collapsed=True, panels=trigger_panels))

# ================= CONSUMER IMPACT (collapsed) =================
consumer_panels = [
    table("Consumer Exposure to Failover",
          "Which consuming applications had their traffic served from a non-primary region. Relevant where data residency or latency commitments apply.",
          GW + FILT +
          "| summarize Calls=count(), Failover=countif(OnFailover),\n"
          "            ['West Europe']=countif(Tier == '3 Tertiary'),\n"
          "            P95=round(percentile(DurationMs, 95))\n"
          "            by Consumer=tostring(apimSubscriptionId_s), Product=tostring(productId_s)\n"
          "| extend ['Failover %'] = round(100.0 * Failover / Calls, 2)\n"
          "| project Consumer, Product, Calls, ['Failover %'], Failover, ['West Europe'], P95\n"
          "| order by Calls desc",
          {"h": 11, "w": 24, "x": 0, "y": 61},
          [dlink("Consumer", "Gateway health for this consumer", "genai-model-operations", "genai-hub-model-operations", "consumer", width=280),
           w("Product", 300), grad("Calls", NEUTRAL, "short", 0, 110),
           gaugecell("Failover %", FAILOVER), grad("P95", LAT, "ms", 0, 100)],
          sort_col="Calls"),

    ts("Hourly Failover Pattern",
       "Failover share bucketed by hour. A repeating daily shape points at capacity limits or scheduled batch load rather than random backend faults.",
       GW + FILT +
       "| summarize Total=count(), Fo=countif(OnFailover) by bin(TimeGenerated, 1h)\n"
       "| project TimeGenerated, ['Failover %'] = 100.0 * Fo / Total\n| order by TimeGenerated asc",
       "percent", {"h": 9, "w": 24, "x": 0, "y": 72},
       extra_over=[{"matcher": {"id": "byName", "options": "Failover %"},
                    "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}}]}]),
]
panels.append(row("Consumer Impact and Patterns", {"h": 1, "w": 24, "x": 0, "y": 40},
                  collapsed=True, panels=consumer_panels))


def var(name, label, query, desc):
    return {"name": name, "label": label, "description": desc, "type": "query", "datasource": DS,
            "query": {"refId": "A", "queryType": "Azure Log Analytics",
                      "azureLogAnalytics": {"query": query, "resource": LAW},
                      "subscription": SUB},
            "definition": label, "refresh": 1, "multi": True, "includeAll": True,
            "allValue": "'*'",
            "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
            "options": [], "sort": 1, "hide": 0}


dashboard = {
    "uid": "genai-regional-failover",
    "title": "GenAI Hub - Regional Failover and Routing",
    "description": ("Shows whether APIM's multi-region failover policy actually routed traffic away "
                    "from Sweden Central. Tiers: Sweden Central primary, East US 2 secondary, "
                    "West Europe tertiary. Region is derived from the backend URL on each gateway log."),
    "tags": ["genai-hub", "production", "failover", "routing", "resilience"],
    "timezone": "browser", "editable": True, "graphTooltip": 1,
    "refresh": "5m", "schemaVersion": 39,
    "time": {"from": "now-7d", "to": "now"},
    "timepicker": {"refresh_intervals": ["1m", "5m", "15m", "30m", "1h", "6h"]},
    "templating": {"list": [
        var("deployment", "Model deployment",
            GW + "| where isnotempty(Dep)\n| distinct Dep\n| order by Dep asc",
            "Filter every panel to one or more model deployments."),
    ]},
    "links": [{"title": "GenAI Hub dashboards", "type": "dashboards", "tags": ["genai-hub"],
               "asDropdown": True, "icon": "external link", "includeVars": False,
               "keepTime": True, "targetBlank": False, "tooltip": "", "url": ""}],
    "panels": panels,
}

out = os.path.join(_OUT, "genai-regional-failover.json")
json.dump(dashboard, open(out, "w"), indent=2)

flat = []
for p in panels:
    flat.append(p)
    flat.extend(p.get("panels", []))
print("panels:", len(flat), "| rows:", sum(1 for p in flat if p["type"] == "row"))
print("written:", out)
