"""RAG query API.

Request path: guardrails -> caller clearance -> embed -> ACL-filtered vector search
-> relevance gate -> grounded generation -> output DLP -> audit log.
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field

from rag_common.dlp import redact
from rag_common.embeddings import embed
from rag_common.logging_setup import log_event, setup_logging, trace_ctx
from rag_common.settings import get_settings

from . import llm, retrieval
from .access import allowed_classifications, caller_email
from .guardrails import check_question

settings = get_settings()
logger: logging.Logger = setup_logging(settings.project_id)

if settings.project_id:
    provider = TracerProvider(resource=Resource.create({"service.name": "rag-api"}))
    provider.add_span_processor(
        BatchSpanProcessor(CloudTraceSpanExporter(project_id=settings.project_id))
    )
    trace.set_tracer_provider(provider)
tracer = trace.get_tracer("rag-api")

app = FastAPI(title="rag-api", docs_url=None, redoc_url=None)
STATIC = Path(__file__).parent / "static"
CLEARANCE = json.loads(settings.clearance_map or "{}")
NO_ANSWER = "I don't have that in the knowledge base."


class AskRequest(BaseModel):
    question: str = Field(max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=12)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    header = request.headers.get("x-cloud-trace-context", "")
    trace_ctx.set(header.split("/")[0] if header else "")
    return await call_next(request)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/")
def ui() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.post("/v1/ask")
def ask(body: AskRequest, request: Request) -> JSONResponse:
    started = time.perf_counter()
    request_id = uuid.uuid4().hex[:12]
    email = caller_email(request.headers)
    allowed = allowed_classifications(email, CLEARANCE, settings.default_clearance)
    timings: dict[str, int] = {}
    outcome, tokens, hits, answer_text, cited = "answered", {}, [], NO_ANSWER, []

    def lap(name: str, t0: float) -> None:
        timings[name] = int((time.perf_counter() - t0) * 1000)

    verdict = check_question(body.question)
    if not verdict.allowed:
        outcome = f"blocked:{verdict.reason}"
    else:
        with tracer.start_as_current_span("embed_query"):
            t0 = time.perf_counter()
            qvec = embed([body.question], "RETRIEVAL_QUERY")[0]
            lap("embed_ms", t0)
        with tracer.start_as_current_span("vector_search"):
            t0 = time.perf_counter()
            candidates = retrieval.search(qvec, allowed, body.top_k or settings.top_k)
            lap("search_ms", t0)
        # Relevance gate: don't ask the model to answer from weak matches.
        hits = [h for h in candidates if h.distance <= settings.max_distance]
        if not hits:
            outcome = "no_relevant_context"
        else:
            with tracer.start_as_current_span("generate"):
                t0 = time.perf_counter()
                answer, tokens = llm.generate(body.question, hits)
                lap("generate_ms", t0)
            if not answer.answerable:
                outcome = "unanswerable"
            else:
                answer_text, _ = redact(answer.answer)
                cited = sorted({n for n in answer.cited_sources if 1 <= n <= len(hits)})

    total_ms = int((time.perf_counter() - started) * 1000)
    citations = [
        {
            "n": n,
            "title": hits[n - 1].doc_title,
            "section": hits[n - 1].heading,
            "uri": hits[n - 1].doc_uri,
            "classification": hits[n - 1].classification,
            "distance": round(hits[n - 1].distance, 4),
        }
        for n in cited
    ]

    log_event(
        logger,
        "ask",
        request_id=request_id,
        outcome=outcome,
        total_ms=total_ms,
        clearance=allowed[-1],
        hits=len(hits),
        **tokens,
        **timings,
    )
    try:
        question_redacted, _ = redact(body.question)
        retrieval.log_query(
            {
                "request_id": request_id,
                "ts": datetime.now(UTC).isoformat(),
                "caller_hash": hashlib.sha256(email.encode()).hexdigest()[:16] if email else "",
                "clearance": allowed[-1],
                "question": question_redacted,
                "outcome": outcome,
                "hits": len(hits),
                "cited_docs": [c["uri"] for c in citations],
                "prompt_tokens": tokens.get("prompt_tokens", 0),
                "output_tokens": tokens.get("output_tokens", 0),
                "total_ms": total_ms,
                "embed_ms": timings.get("embed_ms", 0),
                "search_ms": timings.get("search_ms", 0),
                "generate_ms": timings.get("generate_ms", 0),
            }
        )
    except Exception:  # audit logging must never fail the user's request
        logger.exception("query_log write failed")

    return JSONResponse(
        {
            "request_id": request_id,
            "outcome": outcome,
            "answer": answer_text,
            "citations": citations,
            "clearance": allowed[-1],
            "latency_ms": {"total": total_ms, **timings},
            "usage": tokens,
        }
    )
