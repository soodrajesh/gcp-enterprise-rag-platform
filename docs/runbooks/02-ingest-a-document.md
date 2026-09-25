# 02 · Ingest a document

**When:** adding, updating or removing knowledge; a document is missing from answers.

The **top-level folder is the classification**: `public/`, `internal/`, `confidential/` (anything else → `internal`).

## Add / update
```bash
gcloud storage cp policy.md gs://$PROJECT-rag-docs/internal/policy.md
```
Eventarc fires on `object.finalized`; ingest runs within seconds.

## Verify
```bash
gcloud storage ls -l -r "gs://$PROJECT-rag-docs/**"
```
```
       453  2026-09-25T19:47:42Z  gs://claude-code-507112-rag-docs/confidential/acquisition-memo.md
       491  2026-09-25T19:47:45Z  gs://claude-code-507112-rag-docs/confidential/hr-parental-leave-policy.md
       770  2026-09-25T19:47:50Z  gs://claude-code-507112-rag-docs/internal/engineering-handbook.md
       942  2026-09-25T19:47:53Z  gs://claude-code-507112-rag-docs/internal/incident-response-runbook.md
       863  2026-09-25T19:47:48Z  gs://claude-code-507112-rag-docs/internal/security-policy.md
       523  2026-09-25T19:47:55Z  gs://claude-code-507112-rag-docs/public/company-overview.md
TOTAL: 6 objects, 4042 bytes (3.95kiB)
```
Ingest logs (one structured line per document):
```bash
gcloud logging read 'resource.labels.service_name="rag-ingest" AND jsonPayload.message="document ingested"' \
  --project $PROJECT --limit 3 --format='value(jsonPayload)'
```
```
chunks=3;classification=public;message=document ingested;object=public/company-overview.md;redactions=0
chunks=3;classification=internal;message=document ingested;object=internal/incident-response-runbook.md;redactions=2
```
Chunks in the vector store:
```bash
bqq 'SELECT REPLACE(doc_uri,"gs://'$PROJECT'-rag-docs/","") doc, classification, COUNT(*) chunks, MAX(redactions) redactions FROM rag.chunks GROUP BY 1,2 ORDER BY 1'
```
```
+------------------------------------------+----------------+--------+------------+
|                   doc                    | classification | chunks | redactions |
+------------------------------------------+----------------+--------+------------+
| confidential/acquisition-memo.md         | confidential   |      2 |          2 |
| confidential/hr-parental-leave-policy.md | confidential   |      2 |          2 |
| internal/engineering-handbook.md         | internal       |      3 |          0 |
| internal/incident-response-runbook.md    | internal       |      3 |          2 |
| internal/security-policy.md              | internal       |      3 |          0 |
| public/company-overview.md               | public         |      3 |          0 |
+------------------------------------------+----------------+--------+------------+
```

## Prove PII was redacted *before* storage
```bash
bqq 'SELECT content FROM rag.chunks WHERE REGEXP_CONTAINS(content, r"\[[A-Z_]+\]")'
```
```
Escalation contact for the on-call rota: [CORP_EMAIL], phone [PHONE_NUMBER].
...call Maria O'Brien on [IE_MOBILE]. Employees on payroll can confirm...
...uses test card [CREDIT_CARD_NUMBER].
```
> Names are **not** redacted (`PERSON_NAME` is too noisy at `POSSIBLE` likelihood). Add it with a hotword rule if your policy requires it.

## Reprocess (idempotent)
Re-finalizing the object re-runs ingest; older rows for that document are deleted only *after* the new load succeeds.
```bash
gcloud storage cp gs://$PROJECT-rag-docs/internal/policy.md gs://$PROJECT-rag-docs/internal/policy.md
```

## Remove a document
Deleting the object does **not** remove its chunks (the trigger is `finalized` only). Remove them explicitly:
```bash
gcloud storage rm gs://$PROJECT-rag-docs/internal/policy.md
bqq "DELETE FROM rag.chunks WHERE doc_uri = 'gs://$PROJECT-rag-docs/internal/policy.md'"
```
(Production improvement: also subscribe to `object.deleted`.)

## If it goes wrong
| Symptom | Check |
|---|---|
| Nothing in `rag.chunks` | `gcloud eventarc triggers list --location $REGION` → trigger present? `gcloud logging read 'resource.labels.service_name="rag-ingest" AND severity>=ERROR' --limit 5` |
| `403 ... bigquery.tables.create` | Load job missing `create_disposition=CREATE_NEVER` — see [09 T4](09-troubleshooting.md#t4) |
| Duplicate chunks | Concurrent redelivery; fixed by load-then-delete — [09 T6](09-troubleshooting.md#t6) |
| PII survived | Built-in infoType missed it; add a custom regex infoType — [09 T7](09-troubleshooting.md#t7) |
