# ADR 0001 — BigQuery as the vector store

**Status:** accepted

## Context
A RAG platform needs vector similarity search plus metadata filtering, an audit trail, and analytics on usage. Candidates on GCP: Vertex AI Vector Search, AlloyDB / Cloud SQL with pgvector, BigQuery `VECTOR_SEARCH`.

## Decision
BigQuery, using `VECTOR_SEARCH` over an embedding column, with the ACL predicate applied to the base table.

## Consequences
* **Zero standing cost.** Vertex Vector Search bills for a deployed index endpoint 24×7 (~$70+/month minimum); AlloyDB has a similar floor. BigQuery is pay-per-query and the corpus here is tiny.
* **One system for vectors, audit log, and analytics** (the `v_daily_summary` view, Looker Studio-ready).
* CMEK, column/row governance and IAM at table level come for free.
* **Trade-off:** latency is ~1 s per search, not the ~10 ms of a dedicated ANN service, so it is unsuitable for high-QPS, low-latency serving. Brute-force scan is fine below ~1M chunks; above that add a `TREE_AH` or `IVF` vector index (needs ≥5,000 rows) or graduate the hot path to Vertex Vector Search and keep BigQuery as system of record.
* Pre-filtering the base table means the index is bypassed for filtered queries. Acceptable at this size; at scale, partition by classification and search per partition.

## Alternatives rejected
* **Vertex AI Vector Search** — best latency and scale, but fixed hourly cost is wrong for a demo and for low-volume internal tools.
* **AlloyDB + pgvector** — excellent when the app already needs OLTP; here it would add a stateful, always-on cluster to operate.
