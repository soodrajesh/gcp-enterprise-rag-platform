#!/usr/bin/env bash
# Delete everything this repo created, end to end.
#   ./scripts/down.sh            destroy the platform (keeps the tiny Terraform state bucket)
#   ./scripts/down.sh --purge    also delete the state bucket (nothing of this repo is left)
source "$(dirname "$0")/lib.sh"
need gcloud; need terraform
PURGE=0; [ "${1:-}" = "--purge" ] && PURGE=1

log "Project $PROJECT_ID — destroying all resources managed by this repo"
tf_init; resolve_suffix
# Cloud Run keeps its reserved internal IPs on the subnet for up to ~1h after the services are
# deleted ("resourceInUseByAnotherResource"). It is transient and cannot be forced, so retry.
for attempt in $(seq 1 12); do
  if $TF destroy -input=false -auto-approve 2> >(tee /tmp/rag-destroy.err >&2); then break; fi
  if grep -q "serverless-ipv4-cloudrun\|resourceInUseByAnotherResource" /tmp/rag-destroy.err && [ "$attempt" -lt 12 ]; then
    warn "Cloud Run address reservation still held (attempt $attempt/12); retrying in 5 min"; sleep 300
  else die "terraform destroy failed"; fi
done
ok "platform destroyed"

# Things Terraform cannot fully remove; documented, free or pennies:
#  * KMS key ring + key: GCP never deletes them (key versions are scheduled for destruction). ~$0.
#  * WIF pool: soft-deleted 30 days (the per-deployment suffix means a rebuild does not collide).
rm -f "$SUFFIX_FILE"

if [ "$PURGE" = 1 ]; then
  log "Purging this repo's Terraform state"
  # The state bucket is shared by every repo in this project (one prefix each), so remove only
  # OUR prefix, and the bucket itself only if nothing else is left in it.
  gcloud storage rm -r "gs://$STATE_BUCKET/rag-platform/" --quiet >/dev/null 2>&1 || true
  if [ -z "$(gcloud storage ls "gs://$STATE_BUCKET/" 2>/dev/null)" ]; then
    gcloud storage rm -r "gs://$STATE_BUCKET" --quiet >/dev/null 2>&1 || true; ok "state prefix and (now empty) bucket removed"
  else ok "state prefix removed; bucket kept because other stacks still use it"; fi
fi

log "Anything billable left?"
echo "  Cloud Run:      $(gcloud run services list --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | wc -l | tr -d ' ') services"
echo "  Buckets:        $(gcloud storage buckets list --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | grep -c "$PROJECT_ID-\(rag\|build\)" || true) rag/build buckets"
echo "  BigQuery:       $(bq ls --project_id="$PROJECT_ID" 2>/dev/null | tail -n +3 | grep -c . || true) datasets"
echo "  Artifact repos: $(gcloud artifacts repositories list --project "$PROJECT_ID" --format='value(name)' 2>/dev/null | wc -l | tr -d ' ')"
log "DONE"
