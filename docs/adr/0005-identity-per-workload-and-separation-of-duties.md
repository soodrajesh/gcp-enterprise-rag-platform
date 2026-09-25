# ADR 0005 — One service account per workload; separate plan and deploy identities

**Status:** accepted

## Decision
* `rag-api`, `rag-ingest`, `rag-eventarc`, `rag-build` each get a dedicated SA. Where possible grants are **resource-level** (e.g. `dataViewer` on the `chunks` table only, `dataEditor` on `query_log` only) instead of project-level.
* CI has two identities: `rag-ci-plan` (`viewer` + `securityReviewer`, assumable by any workflow in the repo, including PRs) and `rag-ci-deploy` (run.developer, builds, doc sync; assumable **only** by jobs bound to the protected `prod` GitHub environment).
* Infra `apply` is deliberately *not* done by CI: the deploy identity can ship application versions, not change IAM, networks, or org policy.
* No service-account keys exist; `iam.disableServiceAccountKeyCreation` is enforced.

## Consequences
A compromised PR can read state but not change anything; a compromised app container can't read the audit log or write vectors; privilege escalation via CI requires a human approving the `prod` environment.
