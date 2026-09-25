#!/usr/bin/env python3
"""Evaluate the deployed API against eval/golden.jsonl.

Each clearance level is exercised as a real, distinct identity (a dedicated service
account, impersonated to mint an ID token), so the access-control cases test the
production auth path rather than a test-only backdoor.

    python eval/run_eval.py --url https://rag-api-xxxx.a.run.app \
        --sa-prefix rag-eval --project my-project --out docs/eval-results.md
"""

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

DENIED_OK = {"no_relevant_context", "unanswerable"}


def id_token(sa_email: str, audience: str) -> str:
    return subprocess.run(
        [
            "gcloud",
            "auth",
            "print-identity-token",
            f"--impersonate-service-account={sa_email}",
            f"--audiences={audience}",
            "--include-email",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def ask(url: str, token: str, question: str) -> dict:
    req = urllib.request.Request(
        f"{url}/v1/ask",
        data=json.dumps({"question": question}).encode(),
        headers={"content-type": "application/json", "authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def grade(case: dict, resp: dict) -> list[str]:
    fails = []
    outcome, text = resp["outcome"], resp["answer"].lower()
    cited = " ".join(c["uri"] for c in resp["citations"])
    want = case["expect_outcome"]
    if want == "answered" and outcome != "answered":
        fails.append(f"outcome={outcome}")
    if want == "blocked" and not outcome.startswith("blocked"):
        fails.append(f"outcome={outcome}")
    if want == "no_relevant_context_or_unanswerable" and outcome not in DENIED_OK:
        fails.append(f"outcome={outcome}")
    if case.get("expect_doc") and case["expect_doc"] not in cited:
        fails.append("expected doc not cited")
    for term in case.get("expect_terms", []):
        if term.lower() not in text:
            fails.append(f"missing term {term!r}")
    for term in case.get("forbid_terms", []):
        if term.lower() in text:
            fails.append(f"LEAK: {term!r}")
    if case["clearance"] != "confidential" and "confidential/" in cited:
        fails.append("LEAK: confidential doc cited to lower clearance")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--sa-prefix", default="rag-eval")
    ap.add_argument("--golden", default="eval/golden.jsonl")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    tokens: dict[str, str] = {}
    rows, failed = [], 0
    for line in Path(args.golden).read_text().splitlines():
        case = json.loads(line)
        lvl = case["clearance"]
        if lvl not in tokens:
            sa = f"{args.sa_prefix}-{lvl}@{args.project}.iam.gserviceaccount.com"
            tokens[lvl] = id_token(sa, args.url)
        resp = ask(args.url, tokens[lvl], case["question"])
        fails = grade(case, resp)
        failed += bool(fails)
        rows.append((case, resp, fails))
        mark = "PASS" if not fails else "FAIL"
        print(
            f"{mark}  {case['id']:<24} {lvl:<12} {resp['outcome']:<22} "
            f"{resp['latency_ms']['total']:>5} ms  {'; '.join(fails)}"
        )

    total = len(rows)
    lat = sorted(r[1]["latency_ms"]["total"] for r in rows)
    p50, p95 = lat[len(lat) // 2], lat[min(len(lat) - 1, int(len(lat) * 0.95))]
    print(f"\n{total - failed}/{total} passed · p50 {p50} ms · p95 {p95} ms")

    if args.out:
        md = [
            "# Evaluation results",
            "",
            f"**{total - failed}/{total} cases passed** · p50 {p50} ms · p95 {p95} ms",
            "",
            "| Case | Clearance | Outcome | Latency | Result |",
            "|---|---|---|---|---|",
        ]
        for case, resp, fails in rows:
            result = "✅" if not fails else "❌ " + "; ".join(fails)
            md.append(
                f"| `{case['id']}` | {case['clearance']} | {resp['outcome']} | "
                f"{resp['latency_ms']['total']} ms | {result} |"
            )
        Path(args.out).write_text("\n".join(md) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
