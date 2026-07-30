# GenAI Hub — Observability Implementation & SOP

**Scope:** Azure Managed Grafana observability for the GenAI Hub production platform.
**Subscription:** `161348-Prod01-volvoaihubprod02` — `e4e9074e-0238-41e6-929e-edda76b67e79`
**Primary resource group:** `gaih-prd01-mon-rg`
**Last updated:** 2026-07-30

---

## 1. What exists

### 1.1 Core platform references

| Component | Name | Identifier |
|---|---|---|
| Grafana | `gaih-prd01-grafana0` | `https://gaih-prd01-grafana0-fcgtb3bkb0ftggc7.eus2.grafana.azure.com` |
| Log Analytics | `gaih-prd01-law0` | workspace ID `3098a46a-24e0-4b6c-ab8a-7f2fb17b7881` |
| Model gateway | `gaih-prd01-apim0` | APIM Premium, Sweden Central |
| Grafana datasource | Azure Monitor | uid `azure-monitor-oob` (system-assigned MSI, Monitoring Reader at subscription scope) |

Grafana's only datasource is Azure Monitor. It **cannot** query Cost Management — that is the entire reason the cost pipeline in §2 exists.

### 1.2 Dashboards

Five new dashboards live in the **`GenAI Hub - Preview`** folder (uid `ffto8lqyz7ny8f`). Three existing dashboards were repaired in place.

| Dashboard | uid | Status | Answers |
|---|---|---|---|
| Actual Cost (Live from Azure Billing) | `genai-actual-cost` | New | What did we actually spend? **Source of truth for cost.** |
| Model Operations | `genai-model-operations` | New | Is the model gateway healthy? Which deployments are broken? |
| Regional Failover and Routing | `genai-regional-failover` | New | Did failover route traffic away from Sweden Central? |
| Security Posture | `genai-security-posture` | New | Defender findings, exposure, config drift |
| Token Economics and Chargeback | `genai-token-chargeback` | New | Token consumption per product/consumer. **Cost figures directional only — see §5.2** |
| Model Usage, Cost and Sustainability | `genai-model-usage-cost-sustainability` | Repaired | Unfrozen; now follows time picker |
| GenAI Management View v2 | `genai-management-view-v2` | Repaired | Rolling previous-month panels |
| GenAI Management View | `genai-management-view` | Repaired | Same (stale v1 duplicate — candidate for deletion) |

---

## 2. Cost pipeline — implementation

### 2.1 Why it exists

Grafana cannot query Azure Cost Management. Token-derived cost estimates were measured **81% below actual** (EUR 12,502 estimated vs EUR 66,022 billed for 1–30 Jul), because:

- `AppMetrics` contains **zero Anthropic rows** — Claude was ~EUR 36k of that gap
- Long-context and cache-write meters bill at premium rates no token model represents

This pipeline pulls real billed cost into Log Analytics so Grafana can read it.

### 2.2 Architecture

```
Cost Management API
        │  (daily 03:00 UTC, MSI auth)
        ▼
Logic App  gaih-prd01-model-cost-scan
        │  3 queries → Select shaping → chunked POST (500 rows/batch)
        ▼
DCR  gaih-prd01-modelcost-dcr   (kind: Direct)
        │  stream Custom-GenAIModelCost
        ▼
Table  GenAIModelCost_CL   (gaih-prd01-law0, 365-day retention)
        │
        ▼
Dashboard  genai-actual-cost
```

### 2.3 Component inventory

| Component | Identifier |
|---|---|
| Logic App | `gaih-prd01-model-cost-scan` |
| Logic App MSI (principalId) | `cb9da4ce-58ce-4782-a23c-b73c49312e94` |
| DCR | `gaih-prd01-modelcost-dcr`, `kind: "Direct"` |
| DCR immutableId | `dcr-23413457d1334e1eb3de7e61532b6c5c` |
| DCR ingestion endpoint | `https://gaih-prd01-modelcost-dcr-2wpr-swedencentral.logs.z1.ingest.monitor.azure.com` |
| Stream | `Custom-GenAIModelCost` → `Custom-GenAIModelCost_CL` |
| Table | `GenAIModelCost_CL` |

> **The DCR immutableId and endpoint change every time the DCR is recreated.** See §4.3.

### 2.4 Required role assignments

| Principal | Role | Role definition ID | Scope |
|---|---|---|---|
| Logic App MSI | Cost Management Reader | `72fafb9e-0641-4937-9268-a91bfd8191a3` | Subscription |
| Logic App MSI | Monitoring Metrics Publisher | `3913510d-42f4-4e42-8a64-420c390055eb` | The DCR |

Both are mandatory. The publisher role **must be re-granted after any DCR recreate** — deleting the DCR deletes its role assignments.

### 2.5 The three queries

The scan window rolls: **start of previous month → now**. It is never hardcoded.

| Action | Granularity | Grouping | Rows | Purpose |
|---|---|---|---|---|
| `Query_Daily` | Daily | MeterCategory, MeterSubCategory | ~3,436 | Time-series cost; drives every time-picker panel |
| `Query_Monthly` | Monthly | + Meter | ~490 | Input/output/cache token-type split |
| `Query_Resource` | Monthly | ResourceId, MeterSubCategory | ~428 | Per-AI-account cost (**see §5.1 — not yet populating**) |

Each writes a `Grain` value of `Daily` / `Monthly` / `Resource`.

### 2.6 Table schema

| Column | Type | Notes |
|---|---|---|
| `TimeGenerated` | datetime | **Ingestion** time, not spend date |
| `UsageDate` | datetime | **Real spend date** — filter on this |
| `PeriodStart` / `PeriodEnd` | datetime | Scan window |
| `MeterCategory` / `MeterSubCategory` / `Meter` | string | `MeterSubCategory` ≈ model family |
| `Cost` | real | EUR |
| `UsageQuantity` | real | Unit varies by meter — see §3.3 |
| `Currency` | string | EUR |
| `Grain` | string | `Daily` / `Monthly` / `Resource` |
| `ResourceId` | string | Populated on `Resource` grain only |
| `ScanId` | string | Logic App run name |

---

## 3. Mandatory query conventions

Break these and dashboards silently produce wrong numbers.

### 3.1 Always pin to the latest scan

Every run writes a **complete snapshot**. Summing across scans multiplies cost.

```kusto
let Latest = toscalar(GenAIModelCost_CL | summarize arg_max(TimeGenerated, ScanId) | project ScanId);
GenAIModelCost_CL
| where ScanId == Latest and Grain == 'Daily'
```

### 3.2 Filter on UsageDate, not TimeGenerated

`TimeGenerated` is when the row was ingested (all rows share roughly one timestamp). Set `dashboardTime: false` on the panel target and filter explicitly:

```kusto
| where UsageDate >= $__timeFrom and UsageDate < $__timeTo
```

### 3.3 Two unit conventions in meter names

- Meters containing **"1M Tokens"** → price is per 1,000,000 tokens
- Older meters ending **"Tokens"** → per 1,000 tokens; multiply by 1000 to normalise

Cross-check: Claude Opus 4.5 at EUR 0.0043/1K normalises to EUR 4.30/1M, matching Opus 4.6's EUR 4.24/1M.

### 3.4 Template variable "All" handling

Grafana inserts `allValue` **verbatim, skipping the format function**. So `${var:singlequote}` with All selected yields a bare `*`, producing `Dep in (*)` — a KQL **parse error**, which kills the whole panel. An `or` short-circuit does not save you; KQL parses before it evaluates.

**Correct pattern** — set `allValue` to `'*'` (quoted) and put the sentinel *inside* the list:

```kusto
| where '*' in (${deployment:singlequote}) or Dep in (${deployment:singlequote})
```

| Selection | Renders as | Result |
|---|---|---|
| All | `'*' in ('*') or Dep in ('*')` | First clause true → all rows |
| Specific | `'*' in ('gpt-5.4') or Dep in ('gpt-5.4')` | First false → filter applies |

### 3.5 Never hardcode a period

Use `$__timeFrom` / `$__timeTo`, or for calendar-month panels:

```kusto
let PeriodStart = startofmonth(datetime_add('month', -1, now()));
let PeriodEnd   = startofmonth(now());
```

---

## 4. SOP — routine operations

### 4.1 Daily health check

Open **Actual Cost (Live from Azure Billing)** and read the **Data Age** tile.

| Colour | Meaning | Action |
|---|---|---|
| Green (<30h) | Healthy | None |
| Yellow (30–48h) | One scan missed | Watch |
| Red (>48h) | Pipeline stopped | §4.2 |

CLI equivalent:

```bash
az monitor log-analytics query -w 3098a46a-24e0-4b6c-ab8a-7f2fb17b7881 \
  --analytics-query "GenAIModelCost_CL | summarize LastIngest=max(TimeGenerated), AgeHours=round(datetime_diff('minute', now(), max(TimeGenerated))/60.0,1)" -o table
```

### 4.2 Pipeline stopped — triage

**Step 1 — check recent runs**

```bash
az rest --method get --url "https://management.azure.com/subscriptions/e4e9074e-0238-41e6-929e-edda76b67e79/resourceGroups/gaih-prd01-mon-rg/providers/Microsoft.Logic/workflows/gaih-prd01-model-cost-scan/runs?api-version=2019-05-01&\$top=5" -o json
```

**Step 2 — find the failing action**

```bash
az rest --method get --url "https://management.azure.com/subscriptions/e4e9074e-0238-41e6-929e-edda76b67e79/resourceGroups/gaih-prd01-mon-rg/providers/Microsoft.Logic/workflows/gaih-prd01-model-cost-scan/runs/<RUN_ID>/actions?api-version=2019-05-01" -o json
```

**Step 3 — match the symptom**

| Action / code | Cause | Fix |
|---|---|---|
| `Query_*` → 401/403 | MSI lost Cost Management Reader | Re-grant (§2.4) |
| `Ingest_*` → 403 | MSI lost Monitoring Metrics Publisher on DCR | Re-grant on the DCR |
| `Ingest_*` → `RequestEntityTooLarge` | Chunk size too high | Lower `@chunk(..., 500)` |
| `Ingest_*` → 404 | DCR recreated, Logic App still points at old immutableId | §4.3 |
| Succeeds but rows missing | Cost Management pagination | §4.4 |
| Succeeds but a column is empty | DCR schema cache | §4.3 |

**Step 4 — manual re-run**

```bash
az rest --method post --url "https://management.azure.com/subscriptions/e4e9074e-0238-41e6-929e-edda76b67e79/resourceGroups/gaih-prd01-mon-rg/providers/Microsoft.Logic/workflows/gaih-prd01-model-cost-scan/triggers/Daily_Model_Cost_Scan/run?api-version=2016-06-01"
```

### 4.3 Adding a column — the DCR recreate procedure

> **A DCR's ingestion schema is cached against its `immutableId`.** Updating `streamDeclarations` in place does **nothing** — new columns are accepted by the API and then silently dropped, storing empty values. This is the single most confusing failure mode in this pipeline. Recreation is the only reliable fix.

Order matters:

1. **Add the column to the table**
   `PUT .../workspaces/gaih-prd01-law0/tables/GenAIModelCost_CL?api-version=2022-10-01`
2. **Verify** it via GET before continuing.
3. **Delete the DCR**
   `DELETE .../dataCollectionRules/gaih-prd01-modelcost-dcr?api-version=2023-03-11`
4. **Recreate it** with the new column in `streamDeclarations`, `kind: "Direct"`.
5. **Record the new `immutableId` and `logsIngestion` endpoint** from the response.
6. **Re-grant Monitoring Metrics Publisher** to the Logic App MSI on the new DCR — deleting the DCR deleted the old assignment.
7. **Update the Logic App** ingest URI to the new endpoint + immutableId.
8. **Re-run and verify** the column is populated, not just that the run succeeded.

Verification (a successful run does **not** prove columns landed):

```kusto
GenAIModelCost_CL
| summarize Rows=count(), Populated=countif(isnotempty(<NewColumn>)) by ScanId
| order by ScanId desc | take 2
```

### 4.4 Cost Management pagination — the silent truncation trap

The API caps responses at **5,000 rows** and returns a `nextLink`. It does not error. Exceeding it silently loses data — Daily+Meter grouping once returned EUR 45k of a real EUR 123k.

**Before adding any grouping dimension**, test the row count:

```bash
# check the response for nextLink; if present, the grouping is too fine
az rest --method post \
  --url "https://management.azure.com/subscriptions/e4e9074e-0238-41e6-929e-edda76b67e79/providers/Microsoft.CostManagement/query?api-version=2023-03-01" \
  --headers "Content-Type=application/json" --body @query.json
```

Known-safe groupings:

| Grouping | Granularity | Rows |
|---|---|---|
| MeterCategory + MeterSubCategory | Daily | ~3,436 |
| + Meter | Monthly | ~490 |
| ResourceId + MeterSubCategory | Monthly | ~428 |
| + Meter | **Daily** | **>5,000 — truncates** |

If you need finer detail, either coarsen the granularity or implement `nextLink` following in the Logic App.

### 4.5 Validating a dashboard before publishing

Never trust that a query works because it looks right. Run it through Grafana itself:

```bash
TOKEN=$(az account get-access-token --resource ce34e7e5-485f-4d76-964f-b3d2b16d1e4f --query accessToken -o tsv)
curl -s -X POST "https://gaih-prd01-grafana0-fcgtb3bkb0ftggc7.eus2.grafana.azure.com/api/ds/query" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @payload.json
```

**Substitute template variables with the literal `allValue`**, not a convenient test value. Using `'x'` instead of the real `'*'` once hid a parse error that broke every panel on a dashboard.

### 4.6 Re-deriving token rates

Only needed for the chargeback dashboard's estimate panels. Rates come from actual billing:

```kusto
GenAIModelCost_CL
| where Grain == 'Monthly' and MeterCategory in ('Foundry Models','SaaS','Cognitive Services')
| extend UnitPrice = Cost / UsageQuantity
| project MeterSubCategory, Meter, UnitPrice
```

Normalise per §3.3, then update the `Rates` datatable in the chargeback dashboard's cost panels.

---

## 5. Known issues & open items

### 5.1 `ResourceId` not populating (open)

`Query_Resource` runs, ingests, and totals correctly, but `ResourceId` stores empty. Table schema, DCR stream schema and the Logic App `Select` mapping were all verified correct. Identical symptom to `UsageDate`/`Grain`, which a DCR recreate fixed. Suspected slow table-schema propagation.

**Check:** `GenAIModelCost_CL | where Grain=='Resource' and ResourceId != '' | count`
**If still zero:** repeat §4.3. Until then, the per-AI-account cost panel on the Management Views stays static.

### 5.2 Chargeback cost is now allocated from actual billing (fixed)

`genai-token-chargeback` originally estimated cost as tokens x rates and ran **81% below
actual** (EUR 12,502 vs EUR 66,022 for 1-30 Jul), because `AppMetrics` carries no
Anthropic rows.

**Rebuilt to allocate actual billed cost instead of estimating it.** Totals now reconcile
to the invoice exactly - verified at **EUR 113,708.93 across all three cost panels, 0.00%
variance** over a 60-day window.

Method:

| Family | Allocated by | Why |
|---|---|---|
| Claude | share of `anthropic-api` requests | `AppMetrics` has no Anthropic rows; `GatewayLlmLogs.deploymentName_s` is empty on ~64% of rows |
| OpenAI, Kimi, embeddings | share of tokens (`AppMetrics`) | complete for this family and more precise |

**Remaining limitation:** the total is exact, the per-product split is an *allocation*.
Claude cost is spread by request count, so a product sending long Opus prompts and one
sending short Haiku prompts are charged alike per request. Invoice-grade per-product
Claude cost needs APIM to emit per-request Anthropic token counts (see 5.3).

Note also that Claude requests hit `/anthropic/v1/messages` with **no `/deployments/`
segment** - the model name lives in the request body, which `GatewayLogs` does not
capture. Any deployment-name extraction will silently miss all Claude traffic.


### 5.7 Anthropic token volumes come from billing, not logs

`GatewayLlmLogs` cannot supply Anthropic token counts. Measured over 2 days:

| Row class | Rows | Prompt set | Completion set | Cached set |
|---|---|---|---|---|
| Has `deploymentName_s` | 41,990 | 23,967 (57%) | **0** | **0** |
| No `deploymentName_s` | 73,289 | **0** | **0** | **0** |

Completion and cached tokens are **never** populated. `AppMetrics` carries no Anthropic
rows at all.

**Accurate Anthropic volumes come from billed quantities** in `GenAIModelCost_CL`
(`Grain == 'Monthly'`, which retains `Meter`). One trap: Azure quotes some meters per
**1K** tokens and others per **1M**, and the meter name does not reliably say which -
`paygo-inf-*` meters are per-1M while older `paygo-inference-*` meters are per-1K.

Derive the unit from the meter **name**, not from price magnitude:

```kusto
| extend Unit = case(
    Meter has '1M Tokens',        1000000.0,   // OpenAI meters state the unit
    Meter has 'paygo-inference-', 1000.0,      // older Anthropic plans quote per 1K
    Meter has 'paygo-inf',        1000000.0,   // newer Anthropic plans quote per 1M
    1000.0)
| extend Tokens = UsageQuantity * Unit
```

Two wrong rules were tried first, both of which produced plausible-looking but badly
incorrect output:

- Keying naively on the word `tokens` gave **453 billion** tokens for Claude Opus 4.5
  against EUR 1,945 of spend - off by three orders of magnitude.
- Inferring from price magnitude (`>= 0.1 EUR/unit means per-1M`) looked right for the
  major models but broke on genuinely cheap meters whose real per-1M price is *below*
  EUR 0.10 - cached input and nano models. It reported GPT-5 cache reads at
  **EUR 23.12 per 1M**, more expensive than uncached input.

**Validation rule:** after any change, check that derived rates behave sensibly -
cache read should land near **10% of input** for every family, and Claude output near
**5x input**. If cache read comes out more expensive than input, the unit is wrong.

This is monthly grain, so it does not follow fine time ranges.

### 5.3 `GatewayLlmLogs` telemetry defect (needs APIM owner)

Over 30 days it reported 472M prompt tokens with **`completionTokens_d = 0` and `promptCachedTokens_d = 0`**, while billing showed billions of cache-hit tokens. Two consequences:

- No log source can accurately cost Claude
- **A "0% cache hit rate" reading is a telemetry artefact, not reality.** Prompt caching is enabled and working — cache read is ~EUR 22,314 of actual spend. Do not "fix" caching based on that field.

### 5.4 `Prd-exceptions-la` failing every run

Exception alerting is down. Unrelated to this work, still outstanding.

### 5.5 Broken model deployments

`gpt-5.2-chat_gb_2025-12-11` — 43,535 calls, 100% rejected HTTP 400 at the gateway (no backend code = APIM refuses before reaching a model). Four other deployments in the same state. Visible on **Model Operations → Gateway Rejection Reasons**.

Also seen: a deployment literally named `%7BMODEL%7D` — a client sending an unsubstituted `{MODEL}` placeholder.

### 5.6 Sweden Central underperforming its failover regions

| Tier | Region | Error % | P95 |
|---|---|---|---|
| Primary | Sweden Central | 3.91% | 17,380 ms |
| Secondary | East US 2 | 0.81% | 1,820 ms |
| Tertiary | West Europe | 0% | 307 ms |

East US 2 carries **42.7% of traffic** and is ~10× faster and ~5× more reliable than the primary. Routing priority may warrant review.

---

## 6. Failover reference

Tier order (confirmed by platform owner): **Sweden Central → East US 2 → West Europe**.

Policy fragment `frag-backend-routing` wraps calls in `<retry count="3">` firing on **429 or 5xx**. Routes load from App Configuration `gaih-prd01-appconfig0`, keys `Apim:backendsClusters:{routes,clusters1,clusters2}` (label `Apim`). Failed routes are marked `isThrottling` and **cached up to 3600s**.

**Two things that mislead when reading the dashboard:**

1. **Do not correlate triggers with failover minute-by-minute.** The 1-hour cache means failover persists long after the causing error. Observed: 75–80% failover at 23:00–03:00 with near-zero concurrent 429/5xx.
2. **APIM logs one record per client request**, showing the *final* backend. In-request retries are not logged. Panels show where requests ended up, not how many attempts it took.

Detect the serving region from `backendUrl_s` (`-swc-` / `-eus2-` / `-euw-`). `location_s` is the *APIM* region and is always Sweden Central.

---

## 7. Accepted exceptions

**API-key authentication on model endpoints is an accepted platform decision.** Do not report it as a security finding. The Defender recommendation *"Microsoft Foundry resources should have key access disabled"* is filtered out of `genai-security-posture`; model endpoint auth appears as neutral reference only.

Scope: **model endpoints only.** *"Storage accounts should prevent shared key access"* is a different control and remains a valid finding.

---

## 8. Verification checklist

| # | Check | Where | Expected |
|---|---|---|---|
| 1 | Pipeline fresh | Actual Cost → Data Age | Green, <24h |
| 2 | Claude in cost | Actual Cost → Spend by Family | Opus 4.8, Opus 4.6, Sonnet 4.6 present |
| 3 | Grains reconcile | KQL, Daily vs Monthly totals | Identical |
| 4 | Time picker works | Actual Cost | Values change with range |
| 5 | Rolling months | Management View v2 | Titles read "Previous Month –" |
| 6 | Cost dashboard unfrozen | Model Usage, Cost & Sustainability | Responds to time picker |
| 7 | Failover classification | Regional Failover | Tiers labelled Primary/Secondary/Tertiary |
| 8 | Key-auth excluded | Security Posture | No Foundry key-access finding |

Grain reconciliation query:

```kusto
let L = toscalar(GenAIModelCost_CL | summarize arg_max(TimeGenerated, ScanId) | project ScanId);
GenAIModelCost_CL | where ScanId == L | summarize Cost=round(sum(Cost),2) by Grain
```

All three grains must return the same total. They did at build time: **EUR 122,766.07**.

---

## 9. Caveat on verification performed

Every dashboard was validated by executing its queries through Grafana's `/api/ds/query` endpoint — query correctness and row counts are confirmed. **Rendered pages were not visually inspected**, because the browser tooling available hits an Entra ID sign-in that could not be completed. If a panel renders unexpectedly, the query is verified but the visualisation config may need adjustment.

---

## 10. Drilldown navigation

**Grafana Drilldown apps (Logs/Metrics/Traces) do not work on this instance.** The nav
entry appears because it is core to Grafana 12, and Azure Managed Grafana bundles the
Loki/Prometheus/Tempo/Pyroscope plugins — but only **one datasource is configured**
(Azure Monitor), and Azure Monitor Logs is not a supported Drilldown backend. Opening
Drilldown will show nothing to explore.

To make Metrics Drilldown usable you would need an Azure Monitor Workspace linked to
Grafana (`grafanaIntegrations.azureMonitorWorkspaceIntegrations` is currently empty)
and Managed Prometheus scraping. That is an AKS-shaped path; GenAI Hub runs Container
Apps, and it would not cover APIM or model telemetry.

### What is implemented instead: panel data links

Click a value in a table, land on another dashboard filtered to it, carrying the
current time range.

| From | Field | To | Passes |
|---|---|---|---|
| Model Operations → Model Deployment Health | Deployment | Regional Failover | `var-deployment` |
| Model Operations → Token Economics by Deployment | Deployment | Regional Failover | `var-deployment` |
| Regional Failover → Deployment Routing Matrix | Deployment | Model Operations | `var-deployment` |
| Regional Failover → Consumer Exposure to Failover | Consumer | Model Operations | `var-consumer` |
| Token Chargeback → Model Consumption Detail | Model | Model Operations | `var-deployment` |
| Token Chargeback → Estimated Cost by Model | Model | Model Operations | `var-deployment` |
| Token Chargeback → Consumer Detail | Consumer | Model Operations | `var-consumer` |

URL pattern, via the `dlink()` helper in each builder:

```
/d/<uid>/<slug>?var-<name>=${__value.text}&${__url_time_range}
```

### Value-space caveat (verified 2026-07-30)

A drilldown is only useful if the value exists on the target dashboard. Measured overlap
over a 2-day window:

| Identifier | In both | Gateway only | AppMetrics only |
|---|---|---|---|
| Deployment name | 26 | 7 | 3 |
| Consumer / subscription ID | 18 | 6 | 1 |

Model Operations ↔ Regional Failover links are **exact** — both derive from
`GatewayLogs`. Chargeback links come from `AppMetrics`, so the 3 AppMetrics-only
deployments will land on an empty Model Operations view. That is truthful (there is no
gateway traffic under that name), not a bug.

**Before adding a new drilldown, measure the overlap first.** A link that lands on an
empty dashboard is worse than no link.

## 11. External Service Status — consumer-facing page

Audience is every GenAI Hub user, not the platform team. Two rules follow from that.

### Keep provider detail collapsed

The page carried 96 panels. **Note the 70 per-model tiles do NOT each run a query** — they
read a shared result via the `-- Dashboard --` datasource pointing at panel id 9000. Counting
targets overstates load badly; count only targets whose datasource is not `-- Dashboard --`.

Grafana does not execute queries inside a **collapsed** row until expanded. The seven
per-provider sections (67 tiles) are collapsed by default:

| | Before | After |
|---|---|---|
| Panels on first load | 86 | 25 |
| **Real** datasource queries | 15 | 13 |
| Shared panel references | 67 | 7 |

The saving is mostly **render and scroll**, not query volume — the shared-panel design already
kept query count low. An earlier version of this section claimed an 82 → 16 query reduction;
that was wrong because it counted panel references as queries.

Nothing is hidden — each row header states its model count and expands in one click. **If
you add provider tiles, add them inside a collapsed row.** Uncollapsing these sections
multiplies query load across every concurrent viewer.

### Lead with a plain-language answer

Most visitors want one thing: *can I use it right now?* The full-width banner at the top
answers that in a sentence ("All services operating normally", "Degraded — some requests
are failing, retries advised") rather than as a percentage. Availability figures stay
below for people who want them.

The banner reuses the proven `Overall Service Status` query — gateway success rate bucketed
to 0/1/2/3/4 — and differs only in its value mappings. Do not fork the query; if the
thresholds change, change them once and keep both tiles consistent.

### Guidance panels

The bottom row carries usage guidance, a cost table and troubleshooting. Rates there are
**real, from billing** (see §5.7) — if you edit them, re-derive rather than estimate. The
cost advice follows from the rates: output is ~5x input, cached input ~10% of input, tier
choice is a ~5x lever, long context ~2x.


### Reliability history

Three rolling availability tiles (24h / 7d / 30d) plus a daily series over 60 days, all
scoped to the **model gateway only** (`/deployments/` paths and `anthropic-api`). That
distinction matters: over 30 days the model gateway ran **99.119%** while other platform
APIs ran **97.023%**, so a blended figure understates the service consumers actually call.

**There is deliberately no 90-day figure** — `AzureDiagnostics` retention is 63 days, so a
90-day window silently reports 63 days of data as if it were 90.

The daily chart uses `axisSoftMin` rather than a hard `min`. A hard floor of 95 was tried
first and would have **clipped the worst day off the chart entirely** — observed daily
minimum is 73.78%. On a status page, hiding the bad day is the one thing the chart must not do.

### Finding a model without scrolling

"All models — searchable status" is a filterable table of every model with live availability.
It reads the **same shared panel result** (id 9000) via the `-- Dashboard --` datasource, so it
adds a searchable view at **zero query cost**. Prefer this pattern over adding template
variables — the per-model tiles are static panels and a variable cannot hide them.


### Viewers cannot inspect anything — the page must stand alone

Consumers hold Viewer access. They cannot open a panel's query, use Explore, or follow a
link to an internal dashboard. Everything therefore has to be legible from the rendered
page alone.

Rules for any change to this dashboard:

1. **No dashboard-level link dropdown.** A `links` entry tagged `genai-hub` would advertise
   every internal dashboard (cost, security posture, chargeback) to the whole company.
   This page must keep `links: []`. Audited: currently clean.
2. **No panel data links.** Drilldowns added elsewhere must not be copied here — they lead
   to dashboards consumers cannot open.
3. **No raw column names or internal identifiers** in any visible label, title or
   description. Audited: clean.
4. **Hide plumbing columns.** The shared status panel (id 9000) emits `HealthScore` and
   `TileColor` (raw hex like `#299C46`) to drive the tiles. Any table reading that panel
   **must** hide both — they render as meaningless codes to someone who cannot inspect the
   query. `TileName` should display as `Model`, `AvailabilityPct` as `Availability`, and so on.
5. **Use `noValue` text, not blanks.** An empty availability cell reads as broken; it now
   says "not used recently".

Verification sweep before deploying a change to this page:

```bash
# expect: no dashboard links, no panel links, no technical labels
python3 - <<'PY'
import json,re
d=json.load(open('genai-external-service-status.json'))
print('dashboard links:', d.get('links'))
tech=re.compile(r'TileColor|HealthScore|TileName|_CL\b|_s\b|responseCode|apiId', re.I)
PY
```


### Share query results instead of repeating them

The page-wide pattern: **one panel runs the query, others read its result** via the
`-- Dashboard --` datasource with `panelId`. Grafana executes the source query once and
every referencing panel renders from the same frame.

Applied here:

| Source | Consumers |
|---|---|
| Panel `9000` (per-model status) | 67 provider tiles + the searchable table |
| Panel `9101` (rolling availability, hidden 1x1) | the 24h / 7d / 30d tiles |
| `Overall Service Status` | the top banner |

Query count on this page across the session: **15 -> 13 -> 10**.

Two mechanics worth knowing:

- A referencing panel selects its column with `reduceOptions.fields`, e.g. `/^Last7d$/`.
  The source can therefore return several values in one row and feed several tiles.
- **Panel ids must be unique.** A copied panel keeps the original's `id`, which silently
  breaks `panelId` references - the banner was accidentally created as a duplicate `id: 1`
  alongside `Overall Service Status`. Always assign a fresh id when cloning a panel, and
  check `len(ids) == len(set(ids))` before deploying.

Do not consolidate the remaining pre-existing tiles (`Gateway Availability`,
`Gateway Throttling Rate`) without a reason - they are proven, and rewriting working
consumer-facing panels to save one query each is a poor trade.

### Still open for this page

- An onboarding pointer — new users land here first and there is nothing telling them how
  to get access
