"""Runtime configuration, read once from the environment (12-factor)."""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    project_id: str
    region: str
    llm_location: str
    llm_model: str
    embedding_model: str
    embedding_dim: int
    bq_dataset: str
    chunks_table: str
    query_log_table: str
    dlp_location: str
    dlp_enabled: bool
    top_k: int
    max_distance: float
    clearance_map: str
    default_clearance: str

    @property
    def chunks_fqn(self) -> str:
        return f"{self.project_id}.{self.bq_dataset}.{self.chunks_table}"

    @property
    def query_log_fqn(self) -> str:
        return f"{self.project_id}.{self.bq_dataset}.{self.query_log_table}"


@lru_cache
def get_settings() -> Settings:
    env = os.environ.get
    return Settings(
        project_id=env("PROJECT_ID", ""),
        region=env("REGION", "europe-west1"),
        # Gemini 2.5 is served from the global endpoint only for this project,
        # embeddings + DLP + BigQuery stay regional (see docs/adr/0003).
        llm_location=env("LLM_LOCATION", "global"),
        llm_model=env("LLM_MODEL", "gemini-2.5-flash"),
        embedding_model=env("EMBEDDING_MODEL", "text-embedding-005"),
        embedding_dim=int(env("EMBEDDING_DIM", "768")),
        bq_dataset=env("BQ_DATASET", "rag"),
        chunks_table=env("BQ_CHUNKS_TABLE", "chunks"),
        query_log_table=env("BQ_QUERY_LOG_TABLE", "query_log"),
        dlp_location=env("DLP_LOCATION", "europe-west1"),
        dlp_enabled=env("DLP_ENABLED", "true").lower() == "true",
        top_k=int(env("TOP_K", "6")),
        max_distance=float(env("MAX_DISTANCE", "0.55")),
        clearance_map=env("CLEARANCE_MAP", "{}"),
        default_clearance=env("DEFAULT_CLEARANCE", "public"),
    )
