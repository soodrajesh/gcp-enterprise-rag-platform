# Runbook

## Availability burn
Alert: *RAG API – availability fast/slow burn*.
1. Dashboard → *RAG Platform – Service Health*: is it 5xx from the service or upstream?
2. `gcloud run services logs read rag-api --region europe-west1 --limit 50` and filter `severity>=ERROR`.
3. Upstream quota / outage (Vertex AI, BigQuery)? Check the Google Cloud status page; requests degrade to 5xx because generation is synchronous.
4. Bad revision? `gcloud run services update-traffic rag-api --to-revisions=<previous>=100`.

## Prompt-injection spike
Alert: *prompt-injection attempts spiking*.
```sql
SELECT caller_hash, COUNT(*) n, ARRAY_AGG(DISTINCT outcome) outcomes
FROM `rag.query_log`
WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR) AND STARTS_WITH(outcome, 'blocked')
GROUP BY caller_hash ORDER BY n DESC;
```
Revoke `run.invoker` from the offending identity if it is an insider/service account.

## Document not appearing in answers
1. Object under a classification prefix? (`public/`, `internal/`, `confidential/`; anything else → `internal`.)
2. `gcloud run services logs read rag-ingest` – look for `document ingested` with `chunks`.
3. Eventarc trigger active? `gcloud eventarc triggers describe rag-docs-finalized --location europe-west1`.
4. Reprocess: `gcloud storage cp gs://…/doc.md gs://…/doc.md` (re-finalizes the object; ingest is idempotent).

## Cost spike
`SELECT * FROM rag.v_daily_summary ORDER BY day DESC` – look at `prompt_tokens`. Lower `TOP_K`, or tighten `MAX_DISTANCE`.

## Teardown
`make destroy` (removes all billable resources; KMS key versions are scheduled for destruction).
