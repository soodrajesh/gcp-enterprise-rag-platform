# Cost model

Everything is scale-to-zero / pay-per-use; there is **no always-on compute or load balancer**.

| Component | Driver | Idle | Notes |
|---|---|---|---|
| Cloud Run (api, ingest) | vCPU-s + requests | $0 | `min_instances = 0` |
| BigQuery | bytes scanned | ~$0 | Tiny corpus; storage < 1 MB |
| Vertex embeddings | characters | ~$0 | `text-embedding-005`, a few KB per doc |
| Gemini 2.5 Flash | tokens | $0 | ~1.5–2.5k input tokens per question |
| Cloud DLP | bytes inspected | $0 | Ingest + output, small text |
| Cloud KMS | key versions + ops | ~$0.06/mo | 1 key, 90-day rotation |
| Cloud DNS | zone | ~$0.20/mo | private googleapis.com zone |
| Artifact Registry | GB stored | <$0.10 | cleanup policies cap it |
| VPC flow logs | log volume | ~$0 | 50% sampling on a near-idle subnet |

A budget with alerts at 25/50/90/100% is created by Terraform. Expect well under **$5/month** for a demo; a load test is the main way to move the needle (each question ≈ a fraction of a cent).
