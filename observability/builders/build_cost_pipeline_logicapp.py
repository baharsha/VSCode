import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT = os.path.join(_HERE, "..", "dashboards")

import json

SUB = "e4e9074e-0238-41e6-929e-edda76b67e79"
DCR_EP = "https://gaih-prd01-modelcost-dcr-2wpr-swedencentral.logs.z1.ingest.monitor.azure.com"
DCR_ID = "dcr-23413457d1334e1eb3de7e61532b6c5c"
INGEST_URI = (f"{DCR_EP}/dataCollectionRules/{DCR_ID}"
              "/streams/Custom-GenAIModelCost?api-version=2023-01-01")

# Rolling window: start of PREVIOUS month -> now. Always current, never frozen.
P_START = "@{formatDateTime(addToTime(startOfMonth(utcNow()), -1, 'Month'), 'yyyy-MM-ddTHH:mm:ssZ')}"
P_END = "@{formatDateTime(utcNow(), 'yyyy-MM-ddTHH:mm:ssZ')}"

# UsageDate arrives as an int (20260725). Build ISO via substring - parseDateTime
# with a custom format silently yields null here.
DATE_EXPR = ("@{concat(substring(string(item()[2]),0,4),'-',"
             "substring(string(item()[2]),4,2),'-',"
             "substring(string(item()[2]),6,2),'T00:00:00Z')}")


def cm_query(granularity, dims):
    return {
        "type": "ActualCost", "timeframe": "Custom",
        "timePeriod": {"from": P_START, "to": P_END},
        "dataset": {
            "granularity": granularity,
            "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"},
                            "qty": {"name": "UsageQuantity", "function": "Sum"}},
            "grouping": [{"type": "Dimension", "name": d} for d in dims],
        },
    }


def http_query(granularity, dims):
    return {
        "type": "Http", "runAfter": {},
        "inputs": {
            "method": "POST",
            "uri": (f"https://management.azure.com/subscriptions/{SUB}"
                    "/providers/Microsoft.CostManagement/query?api-version=2023-03-01"),
            "headers": {"Content-Type": "application/json"},
            "body": cm_query(granularity, dims),
            "authentication": {"type": "ManagedServiceIdentity",
                               "audience": "https://management.azure.com/"},
        },
    }


def shape(src, grain, cat_idx, sub_idx, meter_expr, cur_idx, res_expr="@''"):
    return {
        "type": "Select",
        "runAfter": {src: ["Succeeded"]},
        "inputs": {
            "from": f"@body('{src}')?['properties']?['rows']",
            "select": {
                "TimeGenerated": "@utcNow()",
                "PeriodStart": P_START,
                "PeriodEnd": P_END,
                "UsageDate": DATE_EXPR,
                "Cost": "@float(item()[0])",
                "UsageQuantity": "@float(item()[1])",
                "MeterCategory": f"@string(item()[{cat_idx}])",
                "MeterSubCategory": f"@string(item()[{sub_idx}])",
                "Meter": meter_expr,
                "Currency": f"@string(item()[{cur_idx}])",
                "Grain": grain,
                "ResourceId": res_expr,
                "ScanId": "@{workflow()['run']['name']}",
            },
        },
    }


def ingest(name, src):
    return {
        "type": "Foreach",
        "runAfter": {src: ["Succeeded"]},
        "foreach": f"@chunk(body('{src}'), 500)",
        "runtimeConfiguration": {"concurrency": {"repetitions": 1}},
        "actions": {
            f"Post_{name}": {
                "type": "Http", "runAfter": {},
                "inputs": {
                    "method": "POST", "uri": INGEST_URI,
                    "headers": {"Content-Type": "application/json"},
                    "body": "@item()",
                    "authentication": {"type": "ManagedServiceIdentity",
                                       "audience": "https://monitor.azure.com/"},
                },
            }
        },
    }


actions = {
    # Daily by model family - ~3.4k rows, under the 5000-row pagination limit.
    # Drives every time-picker-driven cost panel.
    "Query_Daily": http_query("Daily", ["MeterCategory", "MeterSubCategory"]),
    "Shape_Daily": shape("Query_Daily", "Daily", 3, 4, "@''", 5),
    "Ingest_Daily": ingest("Daily", "Shape_Daily"),
    # Monthly by meter - ~490 rows. Gives input/output/cache token-type detail
    # that daily+meter cannot return without pagination.
    "Query_Monthly": http_query("Monthly", ["MeterCategory", "MeterSubCategory", "Meter"]),
    "Shape_Monthly": shape("Query_Monthly", "Monthly", 3, 4, "@string(item()[5])", 6),
    "Ingest_Monthly": ingest("Monthly", "Shape_Monthly"),
    # Monthly per Azure resource - ~430 rows. Powers per-AI-account cost.
    "Query_Resource": http_query("Monthly", ["ResourceId", "MeterSubCategory"]),
    "Shape_Resource": shape("Query_Resource", "Resource", 4, 4, "@''", 5,
                            res_expr="@string(item()[3])"),
    "Ingest_Resource": ingest("Resource", "Shape_Resource"),
}

definition = {
    "$schema": ("https://schema.management.azure.com/providers/Microsoft.Logic/"
                "schemas/2016-06-01/workflowdefinition.json#"),
    "contentVersion": "1.0.0.0",
    "parameters": {},
    "triggers": {
        "Daily_Model_Cost_Scan": {
            "type": "Recurrence",
            "recurrence": {"frequency": "Day", "interval": 1,
                           "startTime": "2026-08-01T03:00:00Z", "timeZone": "UTC"},
        }
    },
    "actions": actions,
    "outputs": {},
}

payload = {
    "location": "swedencentral",
    "identity": {"type": "SystemAssigned"},
    "tags": {"environment": "prod", "platform": "genai-hub",
             "ID": "161348", "Environment_Type": "Prod"},
    "properties": {"state": "Enabled", "definition": definition, "parameters": {}},
}

out = os.path.join(_HERE, "logicapp.json")
json.dump(payload, open(out, "w"), indent=1)
print("written:", out)
