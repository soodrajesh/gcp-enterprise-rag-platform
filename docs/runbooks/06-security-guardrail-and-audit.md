# 06 · Security: guardrail spike & audit trail

**When:** alert *prompt-injection attempts spiking* (>10 `blocked:*` in 5 min); an auditor asks "who asked what, and what did they see?".

Every request writes one row to `rag.query_log` (partitioned by day, 400-day expiry). The caller is stored as a **hash**, the question **after DLP redaction**.

## Recent activity
```bash
bqq 'SELECT FORMAT_TIMESTAMP("%H:%M:%S", ts) t, clearance, outcome, hits, prompt_tokens pt, output_tokens ot, total_ms, search_ms, generate_ms FROM rag.query_log ORDER BY ts DESC LIMIT 8'
```
```
+----------+--------------+------------------------------------+------+-----+-----+----------+-----------+-------------+
|    t     |  clearance   |              outcome               | hits | pt  | ot  | total_ms | search_ms | generate_ms |
+----------+--------------+------------------------------------+------+-----+-----+----------+-----------+-------------+
| 19:49:01 | internal     | answered                           |    6 | 758 |  49 |     1508 |       740 |         657 |
| 19:48:58 | internal     | blocked:prompt_injection_suspected |    0 |   0 |   0 |        0 |         0 |           0 |
| 19:48:57 | internal     | answered                           |    6 | 739 | 204 |     2195 |       740 |        1348 |
| 19:48:54 | confidential | answered                           |    3 | 447 |  49 |     1483 |       710 |         677 |
| 19:48:51 | internal     | unanswerable                       |    1 | 295 |  36 |     1225 |       707 |         465 |
| 19:48:37 | internal     | answered                           |    6 | 758 |  49 |     1382 |       737 |         561 |
| 19:48:36 | internal     | blocked:prompt_injection_suspected |    0 |   0 |   0 |        0 |         0 |           0 |
| 19:48:36 | confidential | no_relevant_context                |    0 |   0 |   0 |      720 |       644 |           0 |
+----------+--------------+------------------------------------+------+-----+-----+----------+-----------+-------------+
```

## Outcome mix by clearance
```bash
bqq 'SELECT clearance, outcome, COUNT(*) n FROM rag.query_log GROUP BY 1,2 ORDER BY 1,2'
```
```
+--------------+------------------------------------+---+
|  clearance   |              outcome               | n |
+--------------+------------------------------------+---+
| confidential | answered                           | 2 |
| confidential | no_relevant_context                | 1 |
| internal     | answered                           | 7 |
| internal     | blocked:prompt_injection_suspected | 2 |
| internal     | unanswerable                       | 3 |
| public       | answered                           | 1 |
+--------------+------------------------------------+---+
```

## Guardrail spike: who is it?
```bash
bqq "SELECT caller_hash, COUNT(*) n, MIN(ts) first_seen, MAX(ts) last_seen
     FROM rag.query_log
     WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR) AND STARTS_WITH(outcome,'blocked')
     GROUP BY 1 ORDER BY n DESC"
```
Map a hash back to an identity only when you have a legitimate reason — hash candidates you already know:
```bash
python3 -c "import hashlib,sys;print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:16])" someone@example.com
```
**Contain:** remove the identity's invoker role.
```bash
gcloud run services remove-iam-policy-binding rag-api --region $REGION --project $PROJECT \
  --member="serviceAccount:<offender>" --role=roles/run.invoker
```

## Auditor question: "what confidential documents were cited, and to whom?"
```bash
bqq "SELECT clearance, doc, COUNT(*) times
     FROM rag.query_log, UNNEST(cited_docs) doc
     WHERE doc LIKE '%/confidential/%' GROUP BY 1,2 ORDER BY 3 DESC"
```
A row where `clearance != 'confidential'` would be an **access-control breach** → Sev-1. (The eval suite asserts this never happens; the query proves it in production.)

## Daily rollup
```bash
bqq 'SELECT * FROM rag.v_daily_summary'
```
```
+------------+----------+----------+---------+-----------+--------+--------+---------------+---------------+
|    day     | requests | answered | blocked | no_answer | p50_ms | p95_ms | prompt_tokens | output_tokens |
+------------+----------+----------+---------+-----------+--------+--------+---------------+---------------+
| 2026-09-25 |       16 |       10 |       2 |         4 |   1382 |   4810 |          7248 |           885 |
+------------+----------+----------+---------+-----------+--------+--------+---------------+---------------+
```

## Cloud Audit Logs (control-plane trail)
```bash
gcloud logging read 'protoPayload.serviceName="run.googleapis.com" AND protoPayload.methodName:"SetIamPolicy"' \
  --project $PROJECT --limit 5 --format='table(timestamp,protoPayload.authenticationInfo.principalEmail,protoPayload.methodName)'
```

## Limits to remember
Regex guardrails are a first filter, not the security boundary ([threat model](../threat-model.md)). If an attack gets through, the controls that still hold are: ACL in SQL, DLP on output, no tools, no egress.
