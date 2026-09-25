#!/usr/bin/env bash
# Delete everything this repo created, end to end.
#   ./scripts/down.sh            destroy the platform (keeps the tiny Terraform state bucket)
#   ./scripts/down.sh --purge    also delete the state bucket (nothing of this repo is left)
source "$(dirname "$0")/lib.sh"
need gcloud; need terraform
PURGE=0; [ "${1:-}" = "--purge" ] && PURGE=1

log "Project $PROJECT_ID — destroying all resources managed by this repo"
tf_init; resolve_suffix
$TF destroy -input=false -auto-approve
ok "platform destroyed"

# Things Terraform cannot fully remove; documented, free or pennies:
#  * KMS key ring + key: GCP never deletes them (key versions are scheduled for destruction). ~$0.
#  * WIF pool: soft-deleted 30 days (the per-deployment suffix means a rebuild does not collide).
rm -f "$SUFFIX_FILE"

if [ "$PURGE" = 1 ]; then
  log "Purging state bucket"
  gcloud storage rm -r "gs://$STATE_BUCKET" --quiet >/dev/null 2>&1 || true
  ok "state bucket removed"
fi

log "Anything billable left?"
echo "  Cloud Run:      $(gcloud run services list --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | wc -l | tr -d ' ') services"
echo "  Buckets:        $(gcloud storage buckets list --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | grep -c "$PROJECT_ID-\(rag\|build\)" || true) rag/build buckets"
echo "  BigQuery:       $(bq ls --project_id="$PROJECT_ID" 2>/dev/null | tail -n +3 | grep -c . || true) datasets"
echo "  Artifact repos: $(gcloud artifacts repositories list --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | wc -l | tr -d ' ')"
log "DONE"
