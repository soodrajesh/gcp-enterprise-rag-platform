# Runbooks

Every runbook has the same shape: **When** to use it · **Commands** · **Expected output** (captured from the live deployment, project `claude-code-507112`) · **If it goes wrong**.

Set these once per shell:

```bash
export PROJECT=claude-code-507112 REGION=europe-west1
export URL=$(gcloud run services describe rag-api --project $PROJECT --region $REGION --format='value(status.url)')
bqq() { bq query --project_id=$PROJECT --location=$REGION --use_legacy_sql=false --format=pretty "$1"; }
```

| # | Runbook | Use it when |
|---|---------|-------------|
| 01 | [Bootstrap & first deploy](01-bootstrap-and-deploy.md) | Standing the platform up from nothing |
| 02 | [Ingest a document](02-ingest-a-document.md) | Adding/updating/removing knowledge; a doc "isn't found" |
| 03 | [Query the API & verify access control](03-query-and-access-control.md) | Smoke test, proving the ACL works, debugging an answer |
| 04 | [Release & rollback](04-release-and-rollback.md) | Shipping a new image or reverting a bad one |
| 05 | [Availability / latency incident](05-availability-incident.md) | Burn-rate alert fires, users report errors |
| 06 | [Security: guardrail spike & audit](06-security-guardrail-and-audit.md) | Prompt-injection alert, "who asked what?" |
| 07 | [Posture verification](07-posture-verification.md) | Prove the guardrails (CMEK, org policy, egress, IAM) are really on |
| 08 | [Cost & capacity](08-cost-and-capacity.md) | Bill spike, token spend, scaling questions |
| 09 | [Troubleshooting catalogue](09-troubleshooting.md) | Real failures hit while building this, with fixes |
| 10 | [Teardown](10-teardown.md) | Stop all spend |
