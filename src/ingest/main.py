"""Ingestion service: GCS object finalized -> extract -> redact -> chunk -> embed -> BigQuery.

Invoked by Eventarc (CloudEvent, binary content mode). Idempotent: a re-delivered
event for the same object replaces that document's rows rather than duplicating them.
"""

import io
import logging
from datetime import UTC, datetime
from pathlib import PurePosixPath

from fastapi import FastAPI, HTTPException, Request
from google.cloud import bigquery, storage
from pypdf import PdfReader

from rag_common.chunking import chunk_markdown
from rag_common.dlp import redact
from rag_common.embeddings import embed
from rag_common.logging_setup import log_event, setup_logging
from rag_common.settings import get_settings

settings = get_settings()
logger: logging.Logger = setup_logging(settings.project_id)
app = FastAPI(title="rag-ingest", docs_url=None, redoc_url=None)

SUPPORTED = {".md", ".txt", ".pdf"}
CLASSIFICATIONS = {"public", "internal", "confidential"}
bq = bigquery.Client(project=settings.project_id, location=settings.region)
gcs = storage.Client(project=settings.project_id)


def classification_for(object_name: str) -> str:
    """Top-level prefix is the classification: confidential/hr/policy.md -> confidential."""
    top = PurePosixPath(object_name).parts[0] if "/" in object_name else ""
    return top if top in CLASSIFICATIONS else "internal"


def extract_text(name: str, data: bytes) -> str:
    if name.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    return data.decode("utf-8", errors="replace")


def title_for(name: str, text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return PurePosixPath(name).stem.replace("-", " ").replace("_", " ").title()


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/")
async def handle_event(request: Request) -> dict:
    event = await request.json()
    bucket, name = event.get("bucket"), event.get("name")
    generation = int(event.get("generation", 0))
    if not bucket or not name:
        raise HTTPException(400, "not a storage event")

    if PurePosixPath(name).suffix.lower() not in SUPPORTED or name.endswith("/"):
        log_event(logger, "skipped unsupported object", object=name)
        return {"status": "skipped"}

    data = gcs.bucket(bucket).blob(name).download_as_bytes()
    raw = extract_text(name, data)
    text, redactions = redact(raw)
    title = title_for(name, raw)
    chunks = chunk_markdown(text)
    if not chunks:
        log_event(logger, "no extractable text", object=name)
        return {"status": "empty"}

    vectors = embed([f"{title} — {c.heading}\n{c.text}" for c in chunks], "RETRIEVAL_DOCUMENT")
    uri = f"gs://{bucket}/{name}"
    now = datetime.now(UTC).isoformat()
    rows = [
        {
            "chunk_id": f"{name}#{generation}#{c.index}",
            "doc_uri": uri,
            "doc_title": title,
            "doc_generation": generation,
            "classification": classification_for(name),
            "chunk_index": c.index,
            "heading": c.heading,
            "content": c.text,
            "embedding": v,
            "redactions": redactions,
            "ingested_at": now,
        }
        for c, v in zip(chunks, vectors, strict=True)
    ]

    # Replace-then-load keeps re-delivered events idempotent. Load jobs (not streaming
    # inserts) so the DELETE above is never blocked by the streaming buffer.
    bq.query(
        f"DELETE FROM `{settings.chunks_fqn}` WHERE doc_uri = @uri",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("uri", "STRING", uri)]
        ),
    ).result()
    bq.load_table_from_json(
        rows,
        settings.chunks_fqn,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_APPEND"),
    ).result()

    log_event(
        logger,
        "document ingested",
        object=name,
        chunks=len(rows),
        redactions=redactions,
        classification=classification_for(name),
    )
    return {"status": "ingested", "chunks": len(rows), "redactions": redactions}
