#!/usr/bin/env bash
# One-time: create the Terraform state bucket (versioned, uniform access, no public access).
set -euo pipefail
PROJECT="${1:?usage: bootstrap.sh <project-id> [region]}"
REGION="${2:-europe-west1}"
BUCKET="${PROJECT}-tfstate"

gcloud services enable storage.googleapis.com serviceusage.googleapis.com --project "$PROJECT"
if ! gcloud storage buckets describe "gs://${BUCKET}" --project "$PROJECT" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" --project "$PROJECT" --location "$REGION" \
    --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update "gs://${BUCKET}" --versioning
fi
echo "state bucket: gs://${BUCKET}"
echo "terraform -chdir=terraform init -backend-config=\"bucket=${BUCKET}\""
