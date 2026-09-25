"""Cloud DLP de-identification: replace sensitive spans with their infoType label.

Runs on ingest (so PII never lands in the vector store) and again on model
output (defence in depth against a model echoing something it shouldn't).
"""

from functools import lru_cache

from google.cloud import dlp_v2

from .settings import get_settings

INFO_TYPES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD_NUMBER",
    "IBAN_CODE",
    "IRELAND_PPSN",
    "US_SOCIAL_SECURITY_NUMBER",
    "GCP_CREDENTIALS",
    "AWS_CREDENTIALS",
    "AUTH_TOKEN",
]
MAX_ITEM_BYTES = 400_000


@lru_cache
def _client() -> dlp_v2.DlpServiceClient:
    return dlp_v2.DlpServiceClient()


def redact(text: str) -> tuple[str, int]:
    """Return (redacted_text, number_of_findings)."""
    s = get_settings()
    if not s.dlp_enabled or not text.strip():
        return text, 0
    parent = f"projects/{s.project_id}/locations/{s.dlp_location}"
    inspect_config = {
        "info_types": [{"name": n} for n in INFO_TYPES],
        "min_likelihood": dlp_v2.Likelihood.POSSIBLE,
        "include_quote": False,
    }
    deidentify_config = {
        "info_type_transformations": {
            "transformations": [{"primitive_transformation": {"replace_with_info_type_config": {}}}]
        }
    }
    pieces = [text[i : i + MAX_ITEM_BYTES] for i in range(0, len(text), MAX_ITEM_BYTES)]
    out, total = [], 0
    for piece in pieces:
        resp = _client().deidentify_content(
            request={
                "parent": parent,
                "inspect_config": inspect_config,
                "deidentify_config": deidentify_config,
                "item": {"value": piece},
            }
        )
        out.append(resp.item.value)
        total += sum(
            r.item_count for s_ in resp.overview.transformation_summaries for r in s_.results
        )
    return "".join(out), total
