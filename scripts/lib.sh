#!/usr/bin/env bash
# Shared helpers for up.sh / down.sh. Sourced, not executed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m✘ %s\033[0m\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "missing required tool: $1"; }

[ -f "$ROOT/deploy.env" ] && set -a && . "$ROOT/deploy.env" && set +a

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-europe-west1}"
ADMIN_EMAIL="${ADMIN_EMAIL:-$(gcloud config get-value account 2>/dev/null)}"
ALERT_EMAIL="${ALERT_EMAIL:-$ADMIN_EMAIL}"
GITHUB_REPO="${GITHUB_REPO:-soodrajesh/gcp-enterprise-rag-platform}"
BUDGET_AMOUNT="${BUDGET_AMOUNT:-20}"
[ -n "$PROJECT_ID" ] || die "no project: set PROJECT_ID in deploy.env or run 'gcloud config set project'"
BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:-$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingAccountName)' 2>/dev/null | sed 's|billingAccounts/||')}"
[ -n "$BILLING_ACCOUNT_ID" ] || die "project has no billing account linked"

TF="terraform -chdir=$ROOT/terraform"
STATE_BUCKET="${PROJECT_ID}-tfstate"
SUFFIX_FILE="$ROOT/.deploy-suffix"

export TF_VAR_project_id="$PROJECT_ID" TF_VAR_region="$REGION" TF_VAR_billing_account_id="$BILLING_ACCOUNT_ID" \
       TF_VAR_alert_email="$ALERT_EMAIL" TF_VAR_admin_email="$ADMIN_EMAIL" TF_VAR_github_repo="$GITHUB_REPO" \
       TF_VAR_budget_amount="$BUDGET_AMOUNT"

# Currently deployed image for a Cloud Run service ("" if it does not exist yet).
deployed_image() {
  gcloud run services describe "$1" --project "$PROJECT_ID" --region "$REGION" \
    --format='value(spec.template.spec.containers[0].image)' 2>/dev/null || true
}

tf_init() { $TF init -input=false -backend-config="bucket=$STATE_BUCKET" >/dev/null; }

# Suffix rule: a fresh deployment gets a unique suffix; an existing one keeps its own
# (legacy deployments made before the suffix existed have an empty suffix).
resolve_suffix() {
  if [ ! -f "$SUFFIX_FILE" ]; then
    # capture first: `grep -q` closing the pipe early would SIGPIPE terraform under pipefail
    existing="$($TF state list 2>/dev/null || true)"
    if grep -q '^module.kms\.' <<<"$existing"; then : > "$SUFFIX_FILE"
    else printf -- '-%s' "$(date +%y%m%d%H%M)" > "$SUFFIX_FILE"; fi
  fi
  export TF_VAR_resource_suffix="$(cat "$SUFFIX_FILE")"
}
