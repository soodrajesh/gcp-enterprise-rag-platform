# ADR 0003 — Gemini via the global endpoint; everything that stores data stays in `europe-west1`

**Status:** accepted, with a known residency gap

## Context
The project can call Gemini 2.5 Flash on the *global* Vertex AI endpoint but not on a regional EU endpoint. Embeddings, DLP, BigQuery, Cloud Storage and Cloud Run are all regional.

## Decision
* Data at rest (documents, chunks, embeddings, audit log) is EU-only, CMEK-encrypted.
* Generation requests use `location=global`. Prompts contain **already DLP-redacted** chunks only, so the residual exposure is limited to non-sensitive text.
* Model and endpoint are configuration (`LLM_MODEL`, `LLM_LOCATION`), not code.

## Consequences
* Prompts/answers are processed outside the EU for the duration of the call; Vertex does not store them at rest for the customer, but this **is not strict EU processing residency**.
* **If strict residency is a hard requirement:** switch `LLM_LOCATION` to a regional endpoint that serves the chosen model (or use the `eu` multi-region endpoints where available). No code change required.
* DLP on ingest is therefore load-bearing, not cosmetic.
