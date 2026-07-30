import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = os.path.join(_HERE, "..", "dashboards")

import json

SUB = "e4e9074e-0238-41e6-929e-edda76b67e79"
DS = {"type": "grafana-azure-monitor-datasource", "uid": "azure-monitor-oob"}

ASSESS = ("securityresources\n"
          "| where type == 'microsoft.security/assessments'\n"
          "| extend Status = tostring(properties.status.code), "
          "Sev = tostring(properties.metadata.severity), "
          "Rec = tostring(properties.displayName), "
          "Res = tostring(properties.resourceDetails.Id)\n"
          "| extend IsCve = Rec startswith 'Update '\n")

DATA_TYPES = ("'microsoft.cognitiveservices/accounts','microsoft.storage/storageaccounts',"
              "'microsoft.keyvault/vaults','microsoft.documentdb/databaseaccounts',"
              "'microsoft.search/searchservices','microsoft.containerregistry/registries',"
              "'microsoft.appconfiguration/configurationstores','microsoft.cache/redis',"
              "'microsoft.servicebus/namespaces','microsoft.eventhub/namespaces',"
              "'microsoft.dbforpostgresql/flexibleservers','microsoft.sql/servers'")


def q(query, ref="A"):
    return [{
        "refId": ref, "queryType": "Azure Resource Graph", "datasource": DS,
        "subscriptions": [SUB],
        "azureResourceGraph": {"query": query},
    }]


def stat(title, desc, query, steps, gp, unit="short", color_mode="background_solid",
         decimals=0, calc="lastNotNull"):
    return {
        "type": "stat", "title": title, "description": desc, "datasource": DS,
        "gridPos": gp, "targets": q(query),
        "fieldConfig": {"defaults": {
            "unit": unit, "decimals": decimals, "color": {"mode": "thresholds"},
            "thresholds": {"mode": "absolute", "steps": steps}, "mappings": [],
        }, "overrides": []},
        "options": {"colorMode": color_mode, "graphMode": "none", "justifyMode": "center",
                    "orientation": "auto", "textMode": "auto", "wideLayout": True,
                    "showPercentChange": False,
                    "reduceOptions": {"calcs": [calc], "fields": "", "values": False}},
    }


def gauge(title, desc, query, steps, gp, unit="percent", decimals=1):
    return {
        "type": "gauge", "title": title, "description": desc, "datasource": DS,
        "gridPos": gp, "targets": q(query),
        "fieldConfig": {"defaults": {
            "unit": unit, "decimals": decimals, "min": 0, "max": 100,
            "color": {"mode": "thresholds"},
            "thresholds": {"mode": "absolute", "steps": steps}, "mappings": [],
        }, "overrides": []},
        "options": {"showThresholdLabels": False, "showThresholdMarkers": True,
                    "sizing": "auto", "minVizWidth": 75, "minVizHeight": 75,
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
    }


def pie(title, desc, query, gp):
    return {
        "type": "piechart", "title": title, "description": desc, "datasource": DS,
        "gridPos": gp, "targets": q(query),
        "fieldConfig": {"defaults": {
            "unit": "short", "color": {"mode": "palette-classic"},
            "custom": {"hideFrom": {"legend": False, "tooltip": False, "viz": False}},
            "mappings": [],
        }, "overrides": [
            {"matcher": {"id": "byName", "options": "High"},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}}]},
            {"matcher": {"id": "byName", "options": "Medium"},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}}]},
            {"matcher": {"id": "byName", "options": "Low"},
             "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "yellow"}}]},
        ]},
        "options": {"pieType": "donut", "displayLabels": ["value"],
                    "legend": {"displayMode": "list", "placement": "right", "showLegend": True,
                               "values": ["value"]},
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": True},
                    "tooltip": {"mode": "single", "sort": "none"}},
    }


def table(title, desc, query, gp, overrides, sort_col=None):
    opts = {"showHeader": True, "cellHeight": "sm",
            "footer": {"show": False, "reducer": ["sum"], "countRows": False}}
    if sort_col:
        opts["sortBy"] = [{"displayName": sort_col, "desc": True}]
    return {
        "type": "table", "title": title, "description": desc, "datasource": DS,
        "gridPos": gp, "targets": q(query),
        "fieldConfig": {"defaults": {
            "custom": {"align": "auto", "cellOptions": {"type": "auto"},
                       "inspect": False, "filterable": True},
            "color": {"mode": "thresholds"},
            "thresholds": {"mode": "absolute", "steps": [{"color": "text", "value": None}]},
        }, "overrides": overrides},
        "options": opts,
    }


def row(title, gp, collapsed=False, panels=None):
    return {"type": "row", "title": title, "gridPos": gp,
            "collapsed": collapsed, "panels": panels or []}


def sev_override():
    return {
        "matcher": {"id": "byName", "options": "Severity"},
        "properties": [
            {"id": "custom.cellOptions", "value": {"type": "color-text"}},
            {"id": "mappings", "value": [{"type": "value", "options": {
                "High": {"color": "red", "index": 0},
                "Medium": {"color": "orange", "index": 1},
                "Low": {"color": "yellow", "index": 2}}}]},
            {"id": "custom.width", "value": 100},
        ],
    }


def count_override(field, steps, width=110):
    return {
        "matcher": {"id": "byName", "options": field},
        "properties": [
            {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "gradient"}},
            {"id": "thresholds", "value": {"mode": "absolute", "steps": steps}},
            {"id": "custom.width", "value": width},
        ],
    }


def width(field, w):
    return {"matcher": {"id": "byName", "options": field},
            "properties": [{"id": "custom.width", "value": w}]}


SCORE = [{"color": "red", "value": None}, {"color": "orange", "value": 60},
         {"color": "yellow", "value": 75}, {"color": "green", "value": 90}]
HIGH = [{"color": "green", "value": None}, {"color": "red", "value": 1}]
MED = [{"color": "green", "value": None}, {"color": "orange", "value": 1}]
LOW = [{"color": "green", "value": None}, {"color": "yellow", "value": 1}]
EXPOSE = [{"color": "green", "value": None}, {"color": "orange", "value": 1},
          {"color": "red", "value": 5}]
CVE = [{"color": "yellow", "value": None}, {"color": "orange", "value": 10},
       {"color": "red", "value": 25}]

panels = []

# ---------------- POSTURE AT A GLANCE ----------------
panels.append(row("Posture at a Glance", {"h": 1, "w": 24, "x": 0, "y": 0}))

panels.append(gauge(
    "Defender Secure Score",
    "Microsoft Defender for Cloud secure score for this subscription, as a percentage of achievable points.",
    "securityresources\n| where type == 'microsoft.security/securescores'\n"
    "| project Score = round(todouble(properties.score.percentage) * 100, 2)",
    SCORE, {"h": 6, "w": 5, "x": 0, "y": 1}))

panels.append(stat(
    "High Severity", "Unhealthy Defender assessments rated High. Includes both configuration issues and container CVEs.",
    ASSESS + "| where Status == 'Unhealthy' and Sev == 'High'\n| summarize Findings = count()",
    HIGH, {"h": 3, "w": 5, "x": 5, "y": 1}))

panels.append(stat(
    "Medium Severity", "Unhealthy Defender assessments rated Medium.",
    ASSESS + "| where Status == 'Unhealthy' and Sev == 'Medium'\n| summarize Findings = count()",
    MED, {"h": 3, "w": 5, "x": 10, "y": 1}))

panels.append(stat(
    "Config Findings", "Unhealthy findings excluding container/OS package CVEs. These are the ones fixed by changing Azure configuration rather than rebuilding images.",
    ASSESS + "| where Status == 'Unhealthy' and not(IsCve)\n" + "| where not(Rec has 'key access disabled') and not(Rec has 'local authentication') and not(Rec has 'Key access should be disabled')\n" + "| summarize Findings = count()",
    MED, {"h": 3, "w": 5, "x": 5, "y": 4}))

panels.append(stat(
    "Image CVEs", "Unhealthy findings that are container or OS package updates. Fixed by rebuilding and repushing images, not by Azure config.",
    ASSESS + "| where Status == 'Unhealthy' and IsCve\n| summarize Findings = count()",
    CVE, {"h": 3, "w": 5, "x": 10, "y": 4}))

panels.append(stat(
    "Internet-Exposed Services",
    "Data-plane services where publicNetworkAccess is Enabled (or network default action is Allow). Each is reachable from the public internet, subject to its own auth.",
    f"resources\n| where type in~ ({DATA_TYPES})\n"
    "| extend PNA = tostring(coalesce(properties.publicNetworkAccess, properties.networkAcls.defaultAction))\n"
    "| where PNA in ('Enabled','Allow')\n| summarize Exposed = count()",
    EXPOSE, {"h": 6, "w": 4, "x": 15, "y": 1}))

panels.append(stat(
    "Private Endpoints",
    "Private endpoints across the subscription. The platform reaches its data services over the VNet rather than the public internet.",
    "resources\n| where type =~ 'microsoft.network/privateendpoints'\n| summarize Endpoints = count()",
    [{"color": "blue", "value": None}], {"h": 6, "w": 5, "x": 19, "y": 1},
    color_mode="value"))

# ---------------- CONFIGURATION & IDENTITY ----------------
panels.append(row("Configuration and Identity Findings", {"h": 1, "w": 24, "x": 0, "y": 7}))

panels.append(table(
    "Actionable Recommendations",
    "Unhealthy Defender recommendations excluding image CVEs, ranked by number of affected resources. This is the configuration backlog.",
    ASSESS + "| where Status == 'Unhealthy' and not(IsCve)\n"
    "| where not(Rec has 'key access disabled') and not(Rec has 'local authentication') and not(Rec has 'Key access should be disabled')\n"
    "| summarize Affected = count() by Recommendation = Rec, Severity = Sev\n"
    "| order by Affected desc",
    {"h": 11, "w": 16, "x": 0, "y": 8},
    [sev_override(), count_override("Affected", MED, 110), width("Recommendation", 620)],
    sort_col="Affected"))

panels.append(pie(
    "Config Findings by Severity",
    "Severity split of configuration and identity findings, excluding container CVEs.",
    ASSESS + "| where Status == 'Unhealthy' and not(IsCve)\n"
    "| where not(Rec has 'key access disabled') and not(Rec has 'local authentication') and not(Rec has 'Key access should be disabled')\n"
    "| summarize Findings = count() by Severity = Sev",
    {"h": 11, "w": 8, "x": 16, "y": 8}))

# ---------------- NETWORK EXPOSURE ----------------
panels.append(row("Network Exposure", {"h": 1, "w": 24, "x": 0, "y": 19}))

panels.append(table(
    "Internet-Reachable Data Services",
    "Services accepting traffic from the public internet. Compare against the private-endpoint estate: most of this platform is already private, so these are the exceptions worth justifying.",
    f"resources\n| where type in~ ({DATA_TYPES})\n"
    "| extend PNA = tostring(coalesce(properties.publicNetworkAccess, properties.networkAcls.defaultAction))\n"
    "| where PNA in ('Enabled','Allow')\n"
    "| project Resource = name, Service = tostring(split(type,'/')[-1]), "
    "['Resource group'] = resourceGroup, Location = location, Access = PNA\n"
    "| order by Service asc, Resource asc",
    {"h": 10, "w": 14, "x": 0, "y": 20},
    [width("Resource", 300),
     {"matcher": {"id": "byName", "options": "Access"},
      "properties": [
          {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
          {"id": "mappings", "value": [{"type": "value", "options": {
              "Enabled": {"color": "orange", "index": 0},
              "Allow": {"color": "orange", "index": 1}}}]},
          {"id": "custom.width", "value": 110}]}]))

panels.append(table(
    "Private Endpoint Coverage",
    "Private endpoints per resource group. High counts indicate the service estate is reached over the VNet rather than the internet.",
    "resources\n| where type =~ 'microsoft.network/privateendpoints'\n"
    "| summarize ['Private endpoints'] = count() by ['Resource group'] = resourceGroup\n"
    "| order by ['Private endpoints'] desc",
    {"h": 10, "w": 10, "x": 14, "y": 20},
    [count_override("Private endpoints", [{"color": "blue", "value": None}], 150)],
    sort_col="Private endpoints"))

# ---------------- IDENTITY & SECRETS (collapsed) ----------------
identity_panels = [
    table("Model Endpoint Authentication (reference)",
          "Reference only, not a finding. API-key access to model endpoints is an accepted platform decision. This table records which authentication modes are in use so the choice stays visible and intentional.",
          "resources\n| where type =~ 'microsoft.cognitiveservices/accounts'\n"
          "| extend KeyAuth = iff(tostring(properties.disableLocalAuth) == 'true', 'Entra ID only', 'API key allowed')\n"
          "| project Account = name, ['Resource group'] = resourceGroup, Location = location, "
          "Authentication = KeyAuth, ['Public access'] = tostring(properties.publicNetworkAccess)\n"
          "| order by Authentication asc, Account asc",
          {"h": 11, "w": 14, "x": 0, "y": 31},
          [width("Account", 300),
           {"matcher": {"id": "byName", "options": "Authentication"},
            "properties": [
                {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}},
                {"id": "mappings", "value": [{"type": "value", "options": {
                    "API key allowed": {"color": "blue", "index": 0},
                    "Entra ID only": {"color": "blue", "index": 1}}}]},
                {"id": "custom.width", "value": 160}]}]),

    table("Identity and Access Findings",
          "Defender findings relating to identity, permissions and privileged access.",
          ASSESS + "| where Status == 'Unhealthy' and not(IsCve)\n"
          "| where not(Rec has 'key access disabled') and not(Rec has 'local authentication') and not(Rec has 'Key access should be disabled')\n"
          "| where Rec has_any ('identit','permission','privileg','role','authenticat','Key Vault','secret')\n"
          "| summarize Affected = count() by Recommendation = Rec, Severity = Sev\n"
          "| order by Affected desc",
          {"h": 11, "w": 10, "x": 14, "y": 31},
          [sev_override(), count_override("Affected", MED, 100), width("Recommendation", 420)],
          sort_col="Affected"),
]
panels.append(row("Identity and Secrets", {"h": 1, "w": 24, "x": 0, "y": 30},
                  collapsed=True, panels=identity_panels))

# ---------------- CONTAINER VULNERABILITIES (collapsed) ----------------
cve_panels = [
    table("Most Vulnerable Container Images",
          "Container images in the registry carrying the most outstanding package updates. Rebuild and repush these to clear the findings.",
          ASSESS + "| where Status == 'Unhealthy' and IsCve\n"
          "| extend Img = tostring(split(Res, '/')[-1])\n"
          "| summarize ['Outstanding updates'] = count(), "
          "High = countif(Sev == 'High'), Medium = countif(Sev == 'Medium') by Image = Img\n"
          "| order by ['Outstanding updates'] desc\n| take 25",
          {"h": 12, "w": 15, "x": 0, "y": 32},
          [count_override("Outstanding updates", CVE, 170),
           count_override("High", HIGH, 90), count_override("Medium", MED, 100),
           width("Image", 520)],
          sort_col="Outstanding updates"),

    table("Most Common Package Updates",
          "Packages needing an update across the image estate. Fixing the highest-count packages in shared base images clears many findings at once.",
          ASSESS + "| where Status == 'Unhealthy' and IsCve\n"
          "| summarize ['Images affected'] = count() by Package = Rec, Severity = Sev\n"
          "| order by ['Images affected'] desc\n| take 25",
          {"h": 12, "w": 9, "x": 15, "y": 32},
          [sev_override(), count_override("Images affected", CVE, 140), width("Package", 300)],
          sort_col="Images affected"),
]
panels.append(row("Container Image Vulnerabilities", {"h": 1, "w": 24, "x": 0, "y": 31},
                  collapsed=True, panels=cve_panels))

dashboard = {
    "uid": "genai-security-posture",
    "title": "GenAI Hub - Security Posture",
    "description": "Subscription-wide security posture for the GenAI Hub production estate. API-key access to model endpoints is an accepted platform decision and is excluded from findings. Defender for Cloud findings separated into actionable configuration work and container image CVEs, plus live network-exposure and authentication posture from Azure Resource Graph.",
    "tags": ["genai-hub", "production", "security", "posture"],
    "timezone": "browser",
    "editable": True,
    "graphTooltip": 0,
    "refresh": "30m",
    "schemaVersion": 39,
    "time": {"from": "now-24h", "to": "now"},
    "templating": {"list": []},
    "links": [
        {"title": "GenAI Hub dashboards", "type": "dashboards", "tags": ["genai-hub"],
         "asDropdown": True, "icon": "external link", "includeVars": False,
         "keepTime": False, "targetBlank": False, "tooltip": "", "url": ""},
    ],
    "panels": panels,
}

out = os.path.join(_OUT, "genai-security-posture.json")
with open(out, "w") as f:
    json.dump(dashboard, f, indent=2)

flat = []
for p in panels:
    flat.append(p)
    flat.extend(p.get("panels", []))
print("panels:", len(flat), "| rows:", sum(1 for p in flat if p["type"] == "row"))
print("written:", out)
