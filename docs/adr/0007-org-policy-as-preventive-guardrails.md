# ADR 0007 — Preventive guardrails via Organization Policy

**Status:** accepted

## Decision
Enforce, as code (`terraform/org_policy.tf`): no SA key creation/upload, uniform bucket-level access, public-access prevention, `run.managed.requireInvokerIam`, no default network.

## Consequences
* Detective controls (scanners, Security Command Center) tell you after the fact; these make the misconfiguration **impossible**.
* Scoped to the project here because the demo shares an organisation with unrelated projects. In a landing zone these attach to a **folder** so every new project inherits them.
* `constraints/gcp.resourceLocations` was intentionally left off: Gemini's global endpoint (ADR 0003) would be an exception to it.
