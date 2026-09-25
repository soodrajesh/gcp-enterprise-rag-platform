import base64
import json

from api.access import allowed_classifications, caller_email


def _jwt(email):
    body = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).decode().rstrip("=")
    return f"h.{body}.s"


def test_email_from_bearer():
    assert caller_email({"authorization": f"Bearer {_jwt('a@b.c')}"}) == "a@b.c"


def test_email_from_iap_header():
    assert caller_email({"x-goog-authenticated-user-email": "accounts.google.com:a@b.c"}) == "a@b.c"


def test_garbage_token_is_anonymous():
    assert caller_email({"authorization": "Bearer nonsense"}) == ""


def test_clearance_levels_are_cumulative():
    m = {"boss@x": "confidential", "pub@x": "public"}
    full = ["public", "internal", "confidential"]
    assert allowed_classifications("boss@x", m, "internal") == full
    assert allowed_classifications("pub@x", m, "internal") == ["public"]
    assert allowed_classifications("nobody@x", m, "internal") == ["public", "internal"]


def test_unknown_level_fails_closed():
    assert allowed_classifications("a@b", {"a@b": "root"}, "internal") == ["public"]
