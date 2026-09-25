# ADR 0004 — Document-level access control enforced in SQL, identity from the verified token

**Status:** accepted

## Context
The classic RAG failure is retrieving a document the caller must not see and letting the model paraphrase it. Prompt instructions ("don't reveal confidential info") are not an access control.

## Decision
1. Every chunk carries a `classification` (`public` < `internal` < `confidential`) derived from the top-level object prefix at ingest.
2. The API derives the caller's identity from the ID token that Cloud Run/IAP has **already verified** (we only read the `email` claim; nothing is trusted from unauthenticated headers).
3. Identity → clearance is a lookup (config here). The retrieval query filters the **base table** by allowed classifications *before* vector scoring, so disallowed chunks never leave BigQuery.
4. Unknown identities fall back to `public` (fail closed). An unknown level is treated as `public`.

## Consequences
* Verified by the eval suite using three real service-account identities (no test-only bypass) — see `docs/eval-results.md`.
* Production upgrade path: map Cloud Identity **groups** to clearance (Directory API or IAP group claims) instead of a static map, and add row-level security on the table as a second, independent layer.
