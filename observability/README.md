# GenAI Hub Observability

Grafana dashboards and the live cost pipeline for the GenAI Hub production platform
(`161348-Prod01-volvoaihubprod02`).

**Read [SOP.md](SOP.md) first** — it covers architecture, operating procedures,
query conventions, and the failure modes that silently produce wrong numbers.

## Layout

| Path | Contents |
|---|---|
| `SOP.md` | Implementation reference and operational runbook |
| `builders/` | Python generators — the source of truth for each dashboard |
| `dashboards/` | Generated Grafana JSON (regenerate, don't hand-edit) |
| `infra/` | Log Analytics table, DCR, and Logic App definitions |

## Regenerating a dashboard

Builders are deterministic — output goes to `dashboards/`.

```bash
cd builders
python3 build_actual_cost.py
```

| Builder | Dashboard uid |
|---|---|
| `build_actual_cost.py` | `genai-actual-cost` |
| `build_model_operations.py` | `genai-model-operations` |
| `build_regional_failover.py` | `genai-regional-failover` |
| `build_security_posture.py` | `genai-security-posture` |
| `build_token_chargeback.py` | `genai-token-chargeback` |
| `build_cost_pipeline_logicapp.py` | Logic App definition → `infra/` |

`build_token_chargeback.py` reads `builders/models.txt` and `builders/rates.json`.
Rates were derived from actual billing meters — see SOP §4.6 to re-derive them.

## Deploying

```bash
az grafana dashboard update \
  --name gaih-prd01-grafana0 --resource-group gaih-prd01-mon-rg \
  --folder ffto8lqyz7ny8f --overwrite \
  --definition @dashboards/genai-actual-cost.json
```

**Validate before deploying.** Run each query through Grafana's `/api/ds/query`
endpoint and substitute template variables with the literal `allValue` (`'*'`),
not a convenient test value — SOP §4.5 explains why that distinction matters.

## Cost pipeline

`gaih-prd01-model-cost-scan` (Logic App, daily 03:00 UTC) pulls Azure Cost
Management into `GenAIModelCost_CL`, because Grafana's Azure Monitor datasource
cannot query Cost Management directly. This is the only accurate source for model
spend — token-derived estimates exclude Anthropic entirely.

Changing the table schema requires **deleting and recreating the DCR**; updating
it in place silently drops new columns. Follow SOP §4.3 exactly.

## Known issues

See SOP §5. Notably: `ResourceId` is not yet populating on the `Resource` grain,
and a `GatewayLlmLogs` telemetry defect means a "0% cache hit rate" reading is an
artefact — prompt caching is working.
