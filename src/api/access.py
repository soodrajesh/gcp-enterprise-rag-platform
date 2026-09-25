"""Document-level authorisation.

Caller identity comes from the ID token that Cloud Run (or IAP) already verified;
we only read the email claim, we never trust an unauthenticated header. Identity ->
clearance comes from configuration here; in production it would come from Cloud
Identity group membership (see docs/adr/0004).
"""

import base64
import json

LEVELS = ["public", "internal", "confidential"]


def caller_email(headers) -> str:
    iap = headers.get("x-goog-authenticated-user-email", "")
    if iap:
        return iap.split(":", 1)[-1]
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            payload = auth.split(" ", 1)[1].split(".")[1]
            payload += "=" * (-len(payload) % 4)
            return json.loads(base64.urlsafe_b64decode(payload)).get("email", "")
        except (IndexError, ValueError):
            return ""
    return ""


def allowed_classifications(email: str, clearance_map: dict[str, str], default: str) -> list[str]:
    level = clearance_map.get(email, default)
    if level not in LEVELS:
        level = "public"
    return LEVELS[: LEVELS.index(level) + 1]
