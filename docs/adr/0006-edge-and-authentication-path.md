# ADR 0006 — Edge: IAM-authenticated Cloud Run now, external ALB + Cloud Armor + IAP for real users

**Status:** accepted for the demo; production path documented

## Context
Employees need a browser experience; an ID-token-only API suits service callers and demos (`gcloud run services proxy`).

## Decision
The demo exposes Cloud Run with IAM authentication (org policy forbids `allUsers`). For a browser-facing rollout, put a **global external Application Load Balancer** in front with a serverless NEG, **Cloud Armor** (OWASP preconfigured rules, rate limiting, geo policy) and **Identity-Aware Proxy**, then set Cloud Run ingress to `internal-and-cloud-load-balancing`.

## Consequences
* IAP provides the `X-Goog-Authenticated-User-Email` header that `api/access.py` already understands, so no application change is needed.
* Not deployed here because a managed certificate requires a domain and the LB adds a fixed hourly cost that isn't justified for a demo.
