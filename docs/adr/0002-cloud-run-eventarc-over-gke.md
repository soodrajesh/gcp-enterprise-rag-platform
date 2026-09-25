# ADR 0002 — Cloud Run + Eventarc rather than GKE or Dataflow

**Status:** accepted

## Context
Two workloads: a bursty request/response API and an event-driven ingester.

## Decision
Both on Cloud Run (v2), wired by Eventarc (GCS `object.finalized`).

## Consequences
* Scale-to-zero and per-request billing fit spiky internal traffic; no cluster to patch or right-size.
* Eventarc gives at-least-once delivery with retries; the ingester is idempotent (delete-then-load per `doc_uri`).
* Ingress can be `internal-only` for the ingester so nothing but Eventarc can reach it.
* Direct VPC egress replaces the serverless VPC connector (no connector VMs to pay for or scale).
* **Trade-off:** long-running or very large-document ingestion would exceed Cloud Run's request timeout; the migration path is Pub/Sub → Cloud Run Jobs or Dataflow for bulk backfills. The GKE side of the portfolio is covered in the sister repo `gcp-gke-platform-engineering`.
