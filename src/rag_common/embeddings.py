"""Vertex AI embeddings via the google-genai SDK (regional endpoint)."""

from functools import lru_cache

from google import genai
from google.genai import types

from .settings import get_settings

BATCH = 16


@lru_cache
def _client() -> genai.Client:
    s = get_settings()
    return genai.Client(vertexai=True, project=s.project_id, location=s.region)


def embed(texts: list[str], task_type: str) -> list[list[float]]:
    """task_type: RETRIEVAL_DOCUMENT for chunks, RETRIEVAL_QUERY for questions."""
    s = get_settings()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        resp = _client().models.embed_content(
            model=s.embedding_model,
            contents=texts[i : i + BATCH],
            config=types.EmbedContentConfig(
                task_type=task_type, output_dimensionality=s.embedding_dim
            ),
        )
        vectors.extend(e.values for e in resp.embeddings)
    return vectors
