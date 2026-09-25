# 05 · Availability / latency incident

**When:** alert *RAG API – availability fast burn (14.4x / 1h)* or *slow burn (3x / 6h)*, or users report errors/slowness.

**SLOs** (28-day rolling): 99.5% of requests not 5xx · 95% of requests < 10 s.

```
ENABLED  RAG API - availability slow burn (3x / 6h)
ENABLED  RAG API - availability fast burn (14.4x / 1h)
ENABLED  RAG API - prompt-injection attempts spiking
```
| Alert | Meaning | Response |
|---|---|---|
| Fast burn 14.4× / 1h | Whole 28-day budget gone in ~2 days | Page immediately |
| Slow burn 3× / 6h | Budget gone in ~9 days | Ticket, fix this week |

## 1. Scope it (2 min)
```bash
S=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ); E=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -s -G -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: $PROJECT" \
 "https://monitoring.googleapis.com/v3/projects/$PROJECT/timeSeries" \
 --data-urlencode 'filter=metric.type="run.googleapis.com/request_count" AND resource.labels.service_name="rag-api"' \
 --data-urlencode "interval.startTime=$S" --data-urlencode "interval.endTime=$E" \
 --data-urlencode "aggregation.alignmentPeriod=3600s" --data-urlencode "aggregation.perSeriesAligner=ALIGN_SUM" \
 --data-urlencode "aggregation.crossSeriesReducer=REDUCE_SUM" \
 --data-urlencode "aggregation.groupByFields=metric.labels.response_code_class"
```
Healthy example (last hour, includes deliberate 403/blocked probes):
```
2xx 42
4xx 3
```
Or open the dashboard **RAG Platform – Service Health** (requests by class, p50/p95/p99, outcomes, instances).

## 2. Find where the time / errors are
Each `ask` log line carries the stage timings:
```bash
gcloud logging read 'resource.labels.service_name="rag-api" AND jsonPayload.message="ask"' \
  --project $PROJECT --limit 3 --format='value(jsonPayload)'
```
```
clearance=internal;embed_ms=78;generate_ms=799;hits=6;message=ask;outcome=answered;output_tokens=66;prompt_tokens=696;request_id=84da724b0e60;search_ms=462;total_ms=1366
```
Baseline (from the live eval): **embed ≈ 50–90 ms · vector search ≈ 350–750 ms · generate ≈ 450–1,600 ms · p50 ≈ 1.4 s · p95 ≈ 4.8 s**.

| Symptom | Likely cause | Action |
|---|---|---|
| `generate_ms` ≫ 3 s | Vertex/Gemini latency or quota | Check Google Cloud status; lower `max_output_tokens`; retry policy |
| `search_ms` ≫ 2 s | BigQuery slot contention / cold | Check `INFORMATION_SCHEMA.JOBS`; consider a vector index / partitioning ([ADR 0001](../adr/0001-bigquery-as-vector-store.md)) |
| 5xx, logs show `ResourceExhausted` | Vertex quota | Request quota increase; add client-side retry with jitter |
| 5xx right after a deploy | Bad revision | **Roll back** ([04](04-release-and-rollback.md)) — do this *first*, diagnose after |
| 403 from many callers | IAM change removed `run.invoker` | `gcloud run services get-iam-policy rag-api` |
| Cold-start latency after idle | `min_instances = 0` | Set `min_instances = 1` (≈ few €/month) |

## 3. Errors
```bash
gcloud logging read 'resource.labels.service_name="rag-api" AND severity>=ERROR' --project $PROJECT --limit 5 \
  --format='csv[no-heading](timestamp,jsonPayload.message,textPayload)'
```

## 4. Mitigate → communicate → review
1. Mitigate (rollback / raise limits / scale). 2. Update stakeholders every 30 min ([incident policy](../../sample-docs/internal/incident-response-runbook.md)). 3. Blameless review within 5 working days; corrective actions get owners and dates.

## Error-budget check
Console → Monitoring → Services → *RAG API* → SLOs, or:
```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: $PROJECT" \
 "https://monitoring.googleapis.com/v3/projects/$PROJECT/services/rag-api/serviceLevelObjectives" \
 | python3 -c "import sys,json;[print(s['displayName'],'| goal',s['goal']) for s in json.load(sys.stdin)['serviceLevelObjectives']]"
```
```
99.5% of requests are not 5xx (28d) | goal 0.995
95% of requests complete in under 10s (28d) | goal 0.95
```
