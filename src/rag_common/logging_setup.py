"""Structured JSON logging that Cloud Logging parses natively.

`severity`, `message` and `logging.googleapis.com/trace` are special fields; every
other key lands in jsonPayload and can back log-based metrics.
"""

import contextvars
import json
import logging
import sys
import time

trace_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("trace", default="")


class JsonFormatter(logging.Formatter):
    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
        }
        extra = getattr(record, "fields", None)
        if extra:
            entry.update(extra)
        trace = trace_ctx.get()
        if trace and self.project_id:
            entry["logging.googleapis.com/trace"] = f"projects/{self.project_id}/traces/{trace}"
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def setup_logging(project_id: str, level: int = logging.INFO) -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(project_id))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    return logging.getLogger("rag")


def log_event(logger: logging.Logger, message: str, **fields) -> None:
    logger.info(message, extra={"fields": fields})
