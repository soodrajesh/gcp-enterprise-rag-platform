FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src
# non-root, no shell needed at runtime
RUN useradd --system --uid 10001 app && chown -R app /app
USER 10001
ARG SERVICE
ENV SERVICE=${SERVICE}
CMD exec uvicorn ${SERVICE}.main:app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log
