# Threat model

Method: STRIDE over the trust boundaries in [architecture.md](architecture.md), plus the OWASP Top 10 for LLM Applications.

## STRIDE

| Threat | Scenario | Control |
|---|---|---|
| **S**poofing | Caller forges identity to read confidential docs | Identity only from the Cloud Run/IAP-verified ID token; unknown → `public` |
| **T**ampering | Poisoned document alters answers | Uploads restricted to the docs bucket (IAM); versioned bucket; DLP + fencing of retrieved text as data; eval suite includes injection cases |
| **R**epudiation | "I never asked that" | Append-only `query_log` (hashed caller, question, cited docs, tokens); Cloud Audit Logs |
| **I**nformation disclosure | Model leaks PII/confidential text | DLP before storage and after generation; ACL in SQL; CMEK; no public buckets (org policy) |
| **D**enial of service | Token-burning / cost attack | `max_instances`, per-request output cap (800 tokens), input length cap, budget alerts, guardrail short-circuit before any model call |
| **E**levation of privilege | Compromised container pivots | Per-workload SAs with table-level grants, no keys, egress limited to the restricted VIP (no internet route) |

## OWASP LLM Top 10 mapping

| Risk | Status |
|---|---|
| LLM01 Prompt injection (direct) | Pattern guardrail + metric + alert on spikes |
| LLM01 Prompt injection (indirect, via documents) | Retrieved text fenced as untrusted; model has no tools; no egress route |
| LLM02 Sensitive information disclosure | DLP in + out; classification ACL |
| LLM03 Supply chain | Pinned deps, Trivy/Checkov in CI, Artifact Registry vulnerability scanning, immutable tags, SLSA build provenance |
| LLM05 Improper output handling | JSON-schema constrained output; UI renders text nodes (no HTML injection) |
| LLM06 Excessive agency | None: read-only retrieval, no tool calls |
| LLM07 System prompt leakage | Prompt contains no secrets; disclosure requests blocked and answered from context only |
| LLM08 Vector/embedding weaknesses | Access control on the store, per-tenant filter in SQL |
| LLM10 Unbounded consumption | Caps on input, output, instances; budget alert |

## Known gaps (deliberate, documented)
* Guardrail regexes are bypassable; they are a metric and a first filter, not the security boundary.
* Static identity→clearance map (see ADR 0004).
* No VPC Service Controls perimeter: needs an access policy at the org level; noted as the next hardening step.
* Global Gemini endpoint (ADR 0003).
