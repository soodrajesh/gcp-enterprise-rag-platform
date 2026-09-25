#!/usr/bin/env bash
# Build the whole platform end to end: state bucket -> infra -> images -> rollout -> seed -> eval.
# Idempotent: safe to re-run. `--plan` stops after showing the Terraform plan (no changes made).
source "$(dirname "$0")/lib.sh"
PLAN_ONLY=0; [ "${1:-}" = "--plan" ] && PLAN_ONLY=1
need gcloud; need terraform; need python3

log "Project $PROJECT_ID · $REGION · billing $BILLING_ACCOUNT_ID · admin $ADMIN_EMAIL"

log "1/8 Terraform state bucket"
"$ROOT/scripts/bootstrap.sh" "$PROJECT_ID" "$REGION" >/dev/null && ok "gs://$STATE_BUCKET"
tf_init; resolve_suffix; ok "resource suffix: '${TF_VAR_resource_suffix}'"

if [ "$PLAN_ONLY" = 1 ]; then log "Plan only"; $TF plan -input=false; exit 0; fi

log "2/8 Eventarc service agent (avoids first-use permission race)"
gcloud services enable eventarc.googleapis.com --project "$PROJECT_ID" >/dev/null
gcloud beta services identity create --service=eventarc.googleapis.com --project "$PROJECT_ID" >/dev/null 2>&1 || true
ok "ready"

log "3/8 Infrastructure (keeps whatever images are already deployed)"
IMG_ARGS=()
for pair in "rag-api:api_image" "rag-ingest:ingest_image"; do
  cur="$(deployed_image "${pair%%:*}")"
  case "$cur" in ""|*cloudrun/container/hello*) ;; *) IMG_ARGS+=(-var "${pair##*:}=$cur");; esac
done
$TF apply -input=false -auto-approve "${IMG_ARGS[@]+"${IMG_ARGS[@]}"}"
REPO="$($TF output -raw artifact_repo)"; TAG="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo dev)-$(date +%H%M%S)"

log "4/8 Build images with Cloud Build ($TAG)"
gcloud builds submit --project "$PROJECT_ID" --region "$REGION" --config cloudbuild.yaml \
  --service-account "projects/$PROJECT_ID/serviceAccounts/rag-build@$PROJECT_ID.iam.gserviceaccount.com" \
  --gcs-source-staging-dir "gs://${PROJECT_ID}-build-staging/src" \
  --substitutions "_REPO=$REPO,_TAG=$TAG" . >/dev/null
ok "$REPO/{api,ingest}:$TAG"

log "5/8 Roll the images (Terraform-managed, so no drift)"
$TF apply -input=false -auto-approve -var "api_image=$REPO/api:$TAG" -var "ingest_image=$REPO/ingest:$TAG"

log "6/8 Wire GitHub Actions variables (if gh is authenticated)"
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  gh variable set WIF_PROVIDER -R "$GITHUB_REPO" -b "$($TF output -raw wif_provider)" >/dev/null
  gh variable set CI_PLAN_SA -R "$GITHUB_REPO" -b "$($TF output -raw ci_plan_sa)" >/dev/null
  gh variable set CI_DEPLOY_SA -R "$GITHUB_REPO" -b "$($TF output -raw ci_deploy_sa)" >/dev/null
  gh variable set GCP_PROJECT -R "$GITHUB_REPO" -b "$PROJECT_ID" >/dev/null
  gh variable set BILLING_ACCOUNT -R "$GITHUB_REPO" -b "$BILLING_ACCOUNT_ID" >/dev/null
  gh variable set ALERT_EMAIL -R "$GITHUB_REPO" -b "$ALERT_EMAIL" >/dev/null
  ok "repo variables set on $GITHUB_REPO"
else echo "  skipped (gh not installed/authenticated)"; fi

log "7/8 Seed the knowledge base (Eventarc -> ingest)"
gcloud storage rsync -r sample-docs "gs://${PROJECT_ID}-rag-docs" >/dev/null
echo -n "  waiting for ingestion"
for _ in $(seq 1 40); do
  n=$(bq query --project_id="$PROJECT_ID" --location="$REGION" --use_legacy_sql=false --format=csv \
      'SELECT COUNT(DISTINCT doc_uri) FROM rag.chunks' 2>/dev/null | tail -1 || echo 0)
  [ "${n:-0}" -ge 6 ] 2>/dev/null && break; echo -n "."; sleep 5
done; echo; ok "${n:-0}/6 documents ingested"

log "8/8 Evaluate (identity-aware golden set)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
URL="$($TF output -raw api_url)"
.venv/bin/python eval/run_eval.py --project "$PROJECT_ID" --url "$URL" --out docs/eval-results.md

log "DONE"
echo "  API:        $URL   (IAM-protected)"
echo "  Try it:     TOKEN=\$(gcloud auth print-identity-token --audiences=$URL)  # or see docs/runbooks/03"
echo "  Tear down:  ./scripts/down.sh"
