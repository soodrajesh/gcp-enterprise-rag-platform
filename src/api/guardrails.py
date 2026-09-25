"""Input guardrails. Cheap, deterministic, run before any model call.

These are a first layer, not a complete defence: they catch the lazy attacks and
give us a metric. The real controls are architectural (retrieved text is fenced as
untrusted data, the model has no tools, ACL filtering happens in SQL before the
model ever sees a chunk).
"""

import re
from dataclasses import dataclass

MAX_QUESTION_CHARS = 1_000

INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?|rules)",
    r"disregard (all |any )?(the )?(previous|prior|above|system)",
    r"(reveal|print|show|repeat|output) (me )?(your|the) "
    r"(system|hidden|initial) (prompt|instructions)",
    r"you are now (in )?(dan|developer mode|jailbroken)",
    r"act as (an? )?(unrestricted|unfiltered|jailbroken)",
    r"</?(system|instructions?|context)>",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str = ""


def check_question(question: str) -> GuardrailResult:
    q = question.strip()
    if not q:
        return GuardrailResult(False, "empty_question")
    if len(q) > MAX_QUESTION_CHARS:
        return GuardrailResult(False, "question_too_long")
    for pattern in _COMPILED:
        if pattern.search(q):
            return GuardrailResult(False, "prompt_injection_suspected")
    return GuardrailResult(True)
