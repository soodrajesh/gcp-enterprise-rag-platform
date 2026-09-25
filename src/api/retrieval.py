"""Vector retrieval with BigQuery VECTOR_SEARCH.

The classification filter is applied to the *base table* inside the query, so chunks
a caller may not read are never scored, never returned, never sent to the model.
"""

from dataclasses import dataclass

from google.cloud import bigquery

from rag_common.settings import get_settings


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    doc_uri: str
    doc_title: str
    heading: str
    content: str
    classification: str
    distance: float


_client: bigquery.Client | None = None


def _bq() -> bigquery.Client:
    global _client
    if _client is None:
        s = get_settings()
        _client = bigquery.Client(project=s.project_id, location=s.region)
    return _client


def search(query_vector: list[float], allowed: list[str], top_k: int) -> list[Hit]:
    s = get_settings()
    sql = f"""
    SELECT base.chunk_id, base.doc_uri, base.doc_title, base.heading, base.content,
           base.classification, distance
    FROM VECTOR_SEARCH(
      (SELECT * FROM `{s.chunks_fqn}` WHERE classification IN UNNEST(@allowed)),
      'embedding',
      (SELECT @qvec AS embedding),
      top_k => @k,
      distance_type => 'COSINE')
    ORDER BY distance
    """
    job = _bq().query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("allowed", "STRING", allowed),
                bigquery.ArrayQueryParameter("qvec", "FLOAT64", query_vector),
                bigquery.ScalarQueryParameter("k", "INT64", top_k),
            ]
        ),
    )
    return [
        Hit(
            chunk_id=r["chunk_id"],
            doc_uri=r["doc_uri"],
            doc_title=r["doc_title"],
            heading=r["heading"],
            content=r["content"],
            classification=r["classification"],
            distance=float(r["distance"]),
        )
        for r in job.result()
    ]


def log_query(row: dict) -> None:
    s = get_settings()
    errors = _bq().insert_rows_json(s.query_log_fqn, [row])
    if errors:
        raise RuntimeError(f"query_log insert failed: {errors}")
