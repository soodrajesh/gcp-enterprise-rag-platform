# 08 · Cost & capacity

**When:** a budget alert fires, token spend looks wrong, or you're sizing for more users.

## Where the money can go
| Driver | Look at | Lever |
|---|---|---|
| Gemini tokens | `SUM(prompt_tokens), SUM(output_tokens)` in `rag.v_daily_summary` | `TOP_K`, `MAX_DISTANCE`, chunk size, `max_output_tokens` (800) |
| BigQuery scans | `INFORMATION_SCHEMA.JOBS` bytes billed | Cluster/partition, vector index at scale |
| Cloud Run | instance-seconds | `max_instances`, `concurrency`, `min_instances=0` |

## Daily token spend
```bash
bqq 'SELECT day, requests, prompt_tokens, output_tokens FROM rag.v_daily_summary ORDER BY day DESC LIMIT 7'
```
```
|    day     | requests | prompt_tokens | output_tokens |
| 2026-09-25 |       16 |          7248 |           885 |
```
≈ **450 input / 55 output tokens per request** on average (guardrail-blocked and no-context requests cost nothing). Multiply by the current Gemini 2.5 Flash per-token prices to get cost per question (well under a cent at these sizes).

## Bytes billed by queries
```bash
bqq "SELECT FORMAT_TIMESTAMP('%H:%M', creation_time) t, ROUND(total_bytes_billed/1e6,1) AS mb_billed, total_slot_ms
     FROM \`region-$REGION\`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
     WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR) AND statement_type='SELECT'
     ORDER BY creation_time DESC LIMIT 5"
```
```
|   t   | mb_billed | total_slot_ms |
| 19:53 |       0.0 |          NULL |     <- cached results bill nothing
```
Rows with `NULL` slot time are cache hits. For real scans, BigQuery bills a 10 MB minimum per query on-demand — check current [BigQuery pricing](https://cloud.google.com/bigquery/pricing) and multiply by your query volume. At this corpus size the scan is tiny; the cost that scales is Gemini tokens, not BigQuery.

## Budget
```bash
gcloud billing budgets list --billing-account 015C97-F6191B-2F8395
```
```
amount:
  specifiedAmount:
    currencyCode: EUR
    units: '20'
budgetFilter:
  calendarPeriod: MONTH
  creditTypesTreatment: INCLUDE_ALL_CREDITS
  projects:
  - projects/273040233392
displayName: rag-platform monthly guardrail
```
Alerts at 25/50/90/100 % go to the notification channel and billing admins. Account credit balance is visible at Console → Billing → Credits (this project: **€0 of €263 used** when captured).

## Capacity knobs (Terraform `modules/cloud_run_service`)
| Knob | Current | Notes |
|---|---|---|
| `max_instances` | 3 | Hard ceiling on spend and on Vertex QPS |
| `concurrency` | 20 (api), 4 (ingest) | Ingest is CPU/memory-heavy |
| `min_instances` | 0 | Cold start ≈ 2–4 s; set 1 to remove |
| `timeout` | 120 s (api), 300 s (ingest) | Large PDFs need a job-based path ([ADR 0002](../adr/0002-cloud-run-eventarc-over-gke.md)) |

## Load test (careful: this spends tokens)
```bash
for i in $(seq 1 20); do make eval; done   # 220 requests
```
