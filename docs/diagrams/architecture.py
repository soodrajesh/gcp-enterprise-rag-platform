#!/usr/bin/env python3
"""Generates docs/img/architecture.svg (and PNG via docs/diagrams/render.py).

    python3 docs/diagrams/architecture.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from archlib import Diagram  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "img", "architecture.svg")

W, H = 1400, 1262
d = Diagram(W, H, "Enterprise RAG Platform on Google Cloud",
            "Secure, governed GenAI knowledge platform · Cloud Run · Vertex AI · BigQuery vector search · DLP · CMEK · Terraform")

# ── outer boundary: the GCP project / region ────────────────────────────────────────────────────
d.group(190, 96, 1190, 864, "Google Cloud project  ·  region europe-west1 (EU data residency)", "#1a73e8", dash=False,
        fill="#f8faff", label_w=470)

# ── lane labels ──────────────────────────────────────────────────────────────────────────────────
d.band(210, 118, 1150, 215, "QUERY PATH  ·  synchronous", "#1a73e8", "#ffffff")
d.band(210, 353, 1150, 215, "INGESTION PATH  ·  event-driven", "#00897b", "#ffffff")
d.band(210, 588, 1150, 168, "DELIVERY PATH  ·  keyless CI/CD", "#5f6368", "#ffffff")

# VPC strip crossing the query and ingestion lanes (the two Cloud Run services live inside it)
d.group(468, 150, 250, 415, "VPC rag-vpc · no internet route", "#8e44ad", dash=True, fill="#faf5fd", label_w=225)

# ── actors ───────────────────────────────────────────────────────────────────────────────────────
d.node("emp", 96, 250, "Employee", "user", "actor", "browser / API client")
d.node("admin", 96, 470, "Platform team", "user", "actor", "uploads documents")
d.node("gh", 96, 658, "GitHub\nActions", "git", "actor")

# ── QUERY lane (y = 250) ─────────────────────────────────────────────────────────────────────────
d.node("iam", 300, 250, "Cloud Run IAM", "shield", "security", "verified ID token\nclearance from identity")
d.node("api", 520, 250, "Cloud Run\nrag-api", "run", "compute", "guardrails · ACL")
d.small("vip1", 650, 250, "restricted\nVIP", "wall", "network")
d.node("emb", 800, 250, "Vertex AI\nEmbeddings", "sparkle", "ai", "text-embedding-005")
d.node("bq", 960, 250, "BigQuery", "db", "data", "chunks + vectors\n+ query_log")
d.node("gem", 1120, 250, "Vertex AI\nGemini 2.5 Flash", "sparkle", "ai", "grounded, cited")
d.node("dlp", 1280, 250, "Cloud DLP", "filter", "security", "scan output")

d.edge("emp", "iam", "h", num=1, label="request")
d.edge("iam", "api", "h")
d.edge("api", "vip1", "h", dash=True)
d.edge("vip1", "emb", "h", num=2, label="embed query")
d.edge("emb", "bq", "h", num=3, label="ACL-filtered\nsearch")
d.edge("bq", "gem", "h", num=4, label="top-k chunks")
d.edge("gem", "dlp", "h", num=5, label="answer")
# answer returns to the employee along the top of the lane; audit row goes to BigQuery below
d.path([(1280, 220), (1280, 168), (96, 168), (96, 216)], num=7, label="answer + citations", lab_at=(880, 168))
d.path([(520, 220), (520, 200), (960, 200), (960, 220)], num=6, label="audit row: hashed caller, tokens, latency (query_log)", lab_at=(740, 200), dash=True)

# ── INGESTION lane (y = 520) ─────────────────────────────────────────────────────────────────────
d.node("gcs", 250, 470, "Cloud Storage", "bucket", "data", "3 prefixes · CMEK\nversioned")
d.node("eva", 400, 470, "Eventarc", "bolt", "compute", "object.finalized")
d.node("ing", 520, 470, "Cloud Run\nrag-ingest", "run", "compute", "internal-only ingress")
d.small("vip2", 650, 470, "restricted\nVIP", "wall", "network")
d.node("dlp2", 800, 470, "Cloud DLP", "filter", "security", "redact BEFORE storage")
d.node("emb2", 960, 470, "Vertex AI\nEmbeddings", "sparkle", "ai", "chunk vectors")
d.node("bq2", 1120, 470, "BigQuery", "db", "data", "chunks (CMEK)\nload job")
d.node("kms", 1280, 470, "Cloud KMS", "key", "security", "CMEK · 90-day rotation")

d.edge("admin", "gcs", "h", num="A", label="upload", color="#00897b")
d.edge("gcs", "eva", "h", num="B", color="#00897b")
d.edge("eva", "ing", "h", num="C", color="#00897b")
d.edge("ing", "vip2", "h", dash=True, color="#00897b")
d.edge("vip2", "dlp2", "h", num="D", color="#00897b")
d.edge("dlp2", "emb2", "h", num="E", color="#00897b")
d.edge("emb2", "bq2", "h", num="F", color="#00897b")
d.edge("kms", "bq2", "h", color="#d93025", dash=True, label="encrypts (CMEK)", lab_dy=-10)

# ── DELIVERY lane (y = 738) ──────────────────────────────────────────────────────────────────────
d.node("wif", 300, 658, "Workload Identity\nFederation", "key", "security", "OIDC · no SA keys")
d.node("cb", 520, 658, "Cloud Build", "pipeline", "dev", "dedicated SA · SLSA")
d.node("ar", 740, 658, "Artifact Registry", "registry", "dev", "immutable tags · scan")
d.node("run2", 960, 658, "Cloud Run", "run", "compute", "api + ingest revisions")
d.edge("gh", "wif", "h", label="OIDC token", color="#5f6368")
d.edge("wif", "cb", "h", color="#5f6368")
d.edge("cb", "ar", "h", label="push", color="#5f6368")
d.edge("ar", "run2", "h", label="deploy", color="#5f6368")
d.text(1050, 646, "Separate identities:", 12, "#3c4043", "700")
d.text(1050, 664, "plan (read-only) · deploy (gated by", 11.5)
d.text(1050, 680, "the protected `prod` environment).", 11.5)
d.text(1050, 696, "Infra apply is not done by CI.", 11.5)

# ── governance + operations bands ─────────────────────────────────────────────────────────────────
d.band(210, 772, 560, 172, "GOVERNANCE  ·  preventive guardrails", "#d93025", "#fff8f7")
d.node("org", 300, 832, "Org Policy", "policy", "security", "no SA keys · no public\nbuckets · IAM-only Run")
d.node("iam2", 470, 832, "IAM", "shield", "security", "SA per workload\ntable-level grants")
d.node("fw", 640, 832, "VPC egress", "wall", "network", "deny-all + restricted VIP")
d.band(790, 772, 570, 172, "OPERATIONS  ·  SRE + FinOps", "#1e8e3e", "#f6fcf8")
d.node("mon", 870, 832, "Cloud\nMonitoring", "chart", "ops", "SLOs · burn-rate\nalerts · dashboard")
d.node("log", 1010, 832, "Cloud\nLogging", "policy", "ops", "structured JSON\nlog-based metrics")
d.node("trc", 1150, 832, "Cloud Trace", "chart", "ops", "per-stage spans")
d.node("bud", 1290, 832, "Budget", "money", "ops", "alerts 25/50/90/100%")

# ── legends ────────────────────────────────────────────────────────────────────────────────────────
d.legend(34, 976, "Query path (numbered)", [
    ("1", "Caller authenticates: Cloud Run IAM verifies the ID token; clearance derived from identity"),
    ("2", "Guardrails run; query embedded via the restricted VIP (no internet route)"),
    ("3", "BigQuery VECTOR_SEARCH over a base table pre-filtered by classification (ACL in SQL)"),
    ("4", "Relevance gate, then Gemini answers only from the retrieved chunks, with citations"),
    ("5", "Cloud DLP scans the answer; PII/secrets replaced with their infoType"),
    ("6", "Audit row written (hashed caller, tokens, latency, cited docs), 400-day retention"),
    ("7", "Answer and citations returned"),
], w=650)
d.legend(704, 976, "Ingestion path (lettered)", [
    ("A", "A document lands under public/, internal/ or confidential/ (prefix = classification)"),
    ("B", "Eventarc emits object.finalized"),
    ("C", "Delivered to rag-ingest (internal-only ingress; only Eventarc may invoke)"),
    ("D", "DLP redacts PII before anything is stored (custom infoTypes catch what built-ins miss)"),
    ("E", "Chunks embedded (Vertex AI)"),
    ("F", "BigQuery load job; older rows for the document deleted only after success"),
], w=650, color="#00897b")
d.key(34, 1198)
d.text(704, 1170, "Boundaries: project (blue, solid) · VPC (purple, dashed). Red dashed = CMEK encryption.", 11.5)

if __name__ == "__main__":
    d.save(OUT)
    print("wrote", os.path.abspath(OUT))
