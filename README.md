# Enterprise RAG Platform on Google Cloud

A **secure, governed, observable GenAI knowledge platform** — built end to end on GCP with Terraform, deployed and verified live. Not a notebook demo: it treats retrieval-augmented generation as a *platform* problem — identity, data classification, encryption, network egress, SLOs, cost, supply chain and evaluation.

![answer with citations](docs/img/ui-answer-light.png)

<sub>Live output from the deployed service: grounded answer, inline citations, per-stage latency, token usage. Dark mode: [`ui-answer-dark.png`](docs/img/ui-answer-dark.png).</sub>

> The live environment was torn down with `./scripts/down.sh` after the evidence below was captured (screenshots and outputs are from the running system). Rebuild any time with `./scripts/up.sh`.

## What it demonstrates

| Concern | How it's solved here | Proof |
|---|---|---|
| **Access control in RAG** | Chunks carry a classification; the ACL is applied *in the SQL base table* before vector scoring, so a caller's forbidden chunks are never retrieved or shown to the model | [ACL runbook](docs/runbooks/03-query-and-access-control.md), 11/11 eval |
| **PII / secrets** | Cloud DLP redacts **before storage** and again on the model's **output**; custom infoTypes cover what built-ins miss | [ingest runbook](docs/runbooks/02-ingest-a-document.md) |
| **Prompt injection** | Input guardrails (zero-cost short-circuit), retrieved text fenced as untrusted data, model has **no tools**, workloads have **no internet route** | [threat model](docs/threat-model.md) |
| **Data exfiltration** | VPC egress allow-list to the *restricted Google VIP* only — verified with a runtime probe | [posture §4](docs/runbooks/07-posture-verification.md) |
| **Encryption / residency** | CMEK (90-day rotation) on GCS + BigQuery, EU region, public access prevented | [posture §2](docs/runbooks/07-posture-verification.md) |
| **Preventive governance** | Org Policy as code: no SA keys, no public buckets, Cloud Run requires IAM | [ADR 0007](docs/adr/0007-org-policy-as-preventive-guardrails.md) |
| **Keyless CI/CD** | GitHub OIDC → Workload Identity Federation, separate read-only *plan* and gated *deploy* identities | [ADR 0005](docs/adr/0005-identity-per-workload-and-separation-of-duties.md) |
| **Reliability** | SLOs (99.5 % availability, p95 < 10 s), multi-window burn-rate alerts, dashboard, structured logs, Cloud Trace | [incident runbook](docs/runbooks/05-availability-incident.md) |
| **FinOps** | Scale-to-zero everything, per-request token accounting, budget alerts | [cost model](docs/cost.md), [runbook](docs/runbooks/08-cost-and-capacity.md) |
| **Quality** | Golden-set evaluation using **real distinct identities** (no test backdoor) | [`eval/`](eval), [results](docs/eval-results.md) |

## Architecture

```mermaid
flowchart LR
    user([Employee]) -->|"ID token · Cloud Run IAM"| api
    admin([Platform team]) -->|upload docs| gcs
    subgraph gcp["GCP project · europe-west1 · CMEK"]
      direction LR
      subgraph ing["Ingestion (async, event-driven)"]
        gcs[("Cloud Storage<br/>public/ internal/ confidential/")]
        eva["Eventarc<br/>object.finalized"]
        ingest["Cloud Run<br/>rag-ingest<br/>internal-only ingress"]
        dlp1["Cloud DLP<br/>redact"]
        gcs --> eva --> ingest --> dlp1
      end
      subgraph qry["Query (sync)"]
        api["Cloud Run<br/>rag-api"]
        dlp2["Cloud DLP<br/>output scan"]
        api --> dlp2
      end
      bq[("BigQuery<br/>chunks + vectors<br/>audit log")]
      vx["Vertex AI<br/>embeddings · Gemini"]
      ingest -->|embed| vx
      ingest -->|load| bq
      api -->|"embed · generate"| vx
      api -->|"VECTOR_SEARCH<br/>ACL pre-filter"| bq
      vpc{{"VPC · no internet route<br/>egress → restricted.googleapis.com only"}}
      ingest -.-> vpc
      api -.-> vpc
      kms[/"Cloud KMS"/] -.-> gcs
      kms -.-> bq
    end
    api -.-> ops["Monitoring · SLOs · Trace"]
    gh(["GitHub Actions"]) -->|"OIDC → WIF, no keys"| gcp
```

Full request lifecycle, trust boundaries and data flow: [docs/architecture.md](docs/architecture.md).

## Same question, different clearance

The core access-control proof. Both callers are real service-account identities; the API only reads the verified token.

| `internal` clearance | `confidential` clearance |
|---|---|
| ![](docs/img/ui-acl-internal-denied.png) | ![](docs/img/ui-acl-confidential-allowed.png) |
| Confidential chunks filtered in SQL — model sees 1 weak hit, declines | Same query returns the cited HR policy |

## Guardrails at work

| Prompt injection blocked (0 ms, no model call) | PII redacted in the answer |
|---|---|
| ![](docs/img/ui-guardrail-blocked.png) | ![](docs/img/ui-dlp-redacted-output.png) |

## Evaluation (live, 11 cases)

```
PASS  sev1-steps               internal     answered                4810 ms
PASS  pw-rotation              internal     answered                1527 ms
PASS  log-retention            internal     answered                1462 ms
PASS  slo-tier1                internal     answered                1371 ms
PASS  support-hours            public       answered                1546 ms
PASS  leave-confidential-ok    confidential answered                1574 ms
PASS  leave-acl-denied         internal     unanswerable            1366 ms
PASS  acquisition-acl-denied   internal     unanswerable            1312 ms
PASS  out-of-scope             confidential no_relevant_context      720 ms
PASS  injection                internal     blocked:prompt_injection_suspected     0 ms
PASS  pii-not-leaked           internal     answered                1382 ms
11/11 passed · p50 1382 ms · p95 4810 ms
```

## Proof the guardrails are real, not just configured

```
$ gcloud org-policies list --project $PROJECT
iam.disableServiceAccountKeyCreation   SET      run.managed.requireInvokerIam   SET
storage.publicAccessPrevention         SET      storage.uniformBucketLevelAccess SET

# runtime egress probe: same VPC config, same service account as the ingest service
dns storage.googleapis.com -> 199.36.153.4                                        # restricted VIP
https://example.com -> BLOCKED: URLError [Errno 101] Network is unreachable       # no internet route
https://storage.googleapis.com/storage/v1/b/none -> reachable, HTTP 401           # Google APIs still work
```

Every command above has a runbook with the **exact commands and captured outputs**: [docs/runbooks](docs/runbooks/README.md).

## Key design decisions (ADRs)

| # | Decision | Trade-off called out |
|---|---|---|
| [0001](docs/adr/0001-bigquery-as-vector-store.md) | BigQuery as the vector store | ~1 s search vs. ~10 ms for a dedicated ANN service; zero standing cost |
| [0002](docs/adr/0002-cloud-run-eventarc-over-gke.md) | Cloud Run + Eventarc, not GKE/Dataflow | Large-document path needs Jobs/Dataflow |
| [0003](docs/adr/0003-gemini-global-endpoint-regional-data.md) | Gemini on the global endpoint, data at rest in EU | **Known residency gap**, documented with the switch |
| [0004](docs/adr/0004-clearance-in-sql-identity-from-token.md) | ACL enforced in SQL from verified identity | Static map → groups in production |
| [0005](docs/adr/0005-identity-per-workload-and-separation-of-duties.md) | SA per workload; plan ≠ deploy ≠ apply | CI can't change IAM/network |
| [0006](docs/adr/0006-edge-and-authentication-path.md) | IAM auth now; ALB + Cloud Armor + IAP for browsers | Needs a domain + fixed LB cost |
| [0007](docs/adr/0007-org-policy-as-preventive-guardrails.md) | Org Policy as preventive controls | Project-scoped here; folder-scoped in a landing zone |

## Real problems found and fixed while building it

Written up in [the troubleshooting catalogue](docs/runbooks/09-troubleshooting.md) — a delete-then-load **race** producing duplicate vectors under at-least-once delivery, DLP built-ins **missing** `.example` emails and local phone formats, a least-privilege-breaking BigQuery load default, a wrong org-policy constraint name, and more. The fixes are in the code.

## Quick start

```bash
git clone https://github.com/soodrajesh/gcp-enterprise-rag-platform && cd gcp-enterprise-rag-platform
gcloud config set project <your-project>   # billing linked; everything else is auto-detected
./scripts/up.sh      # state bucket → 120+ resources → images → rollout → seed → eval (expect 11/11)
./scripts/down.sh    # destroy everything this repo created (--purge also drops the state bucket)
```
`./scripts/up.sh --plan` shows the Terraform plan without changing anything. Optional overrides: [`deploy.env.example`](deploy.env.example).
Step-by-step with expected output: [runbook 01](docs/runbooks/01-bootstrap-and-deploy.md). Teardown details: [runbook 10](docs/runbooks/10-teardown.md).

**Cost:** everything scales to zero; a demo month is a few euros. Budget alerts are created by Terraform.

## Repository layout

```
src/api/          FastAPI query service (guardrails, ACL, retrieval, grounded generation, audit)
src/ingest/       Eventarc-driven ingestion (extract → DLP → chunk → embed → BigQuery)
src/rag_common/   shared: settings, JSON logging, chunking, embeddings, DLP
terraform/        root + modules: kms, network, data_platform, cloud_run_service, observability, github_wif
eval/             golden set + identity-aware evaluation harness
docs/             architecture, 7 ADRs, threat model (STRIDE + OWASP LLM Top 10), cost, runbooks
.github/          CI (lint, test, Checkov, Trivy, WIF plan) and gated deploy
```

## Known gaps (deliberate)

No VPC Service Controls perimeter (needs an org access policy); regex guardrails are a first filter, not the boundary; static identity → clearance map; vector index omitted below the 5k-row minimum. See the [threat model](docs/threat-model.md).

## License

MIT
