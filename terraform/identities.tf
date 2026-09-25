# One service account per workload, each with only what it needs (see docs/adr/0005).

locals {
  sa_ids      = ["rag-api", "rag-ingest", "rag-eventarc", "rag-build", "rag-ci-plan", "rag-ci-deploy"]
  eval_levels = ["public", "internal", "confidential"]
}

resource "google_service_account" "workload" {
  for_each     = toset(local.sa_ids)
  project      = var.project_id
  account_id   = each.value
  display_name = each.value
  depends_on   = [google_project_service.apis]
}

# Test identities, one per clearance level, so the eval suite exercises real auth.
resource "google_service_account" "eval" {
  for_each     = toset(local.eval_levels)
  project      = var.project_id
  account_id   = "rag-eval-${each.value}"
  display_name = "Eval identity (${each.value} clearance)"
  depends_on   = [google_project_service.apis]
}

locals {
  sa      = { for k, v in google_service_account.workload : k => v.email }
  eval_sa = { for k, v in google_service_account.eval : k => v.email }

  # identity -> clearance, injected into the API. Unknown callers fall back to "public".
  clearance_map = merge(
    { (var.admin_email) = "confidential" },
    { for k, v in local.eval_sa : v => k },
  )
}

# --- Project-level roles for runtime identities ----------------------------------------
locals {
  project_roles = {
    "rag-api" = [
      "roles/aiplatform.user",
      "roles/bigquery.jobUser",
      "roles/dlp.user",
      "roles/logging.logWriter",
      "roles/cloudtrace.agent",
      "roles/monitoring.metricWriter",
    ]
    "rag-ingest" = [
      "roles/aiplatform.user",
      "roles/bigquery.jobUser",
      "roles/dlp.user",
      "roles/logging.logWriter",
    ]
    "rag-eventarc" = ["roles/eventarc.eventReceiver"]
    "rag-build" = [
      "roles/artifactregistry.writer",
      "roles/logging.logWriter",
    ]
    "rag-ci-plan" = [
      "roles/viewer",
      "roles/iam.securityReviewer",
      "roles/serviceusage.serviceUsageConsumer",
    ]
    "rag-ci-deploy" = [
      "roles/run.developer",
      "roles/cloudbuild.builds.editor",
      "roles/serviceusage.serviceUsageConsumer",
      "roles/logging.viewer",
    ]
  }

  project_role_pairs = flatten([
    for sa, roles in local.project_roles : [
      for r in roles : { sa = sa, role = r }
    ]
  ])
}

resource "google_project_iam_member" "workload" {
  for_each = { for p in local.project_role_pairs : "${p.sa}:${p.role}" => p }
  project  = var.project_id
  role     = each.value.role
  member   = "serviceAccount:${local.sa[each.value.sa]}"
}

# --- Resource-level (tighter than project-level) grants -----------------------------------
resource "google_storage_bucket_iam_member" "ingest_reads_docs" {
  bucket = module.data.docs_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${local.sa["rag-ingest"]}"
}

resource "google_storage_bucket_iam_member" "deploy_syncs_docs" {
  bucket = module.data.docs_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.sa["rag-ci-deploy"]}"
}

resource "google_bigquery_table_iam_member" "api_reads_chunks" {
  project    = var.project_id
  dataset_id = module.data.dataset_id
  table_id   = module.data.chunks_table_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${local.sa["rag-api"]}"
}

resource "google_bigquery_table_iam_member" "api_writes_audit" {
  project    = var.project_id
  dataset_id = module.data.dataset_id
  table_id   = module.data.query_log_table_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${local.sa["rag-api"]}"
}

resource "google_bigquery_table_iam_member" "ingest_writes_chunks" {
  project    = var.project_id
  dataset_id = module.data.dataset_id
  table_id   = module.data.chunks_table_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${local.sa["rag-ingest"]}"
}

# Direct GCS -> Eventarc triggers need the GCS service agent to publish to Pub/Sub.
data "google_storage_project_service_account" "gcs" {
  project    = var.project_id
  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "gcs_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}

# --- Delegation ---------------------------------------------------------------------------
# Deployer may act as the runtime + build identities (needed to roll Cloud Run / run builds).
resource "google_service_account_iam_member" "deploy_acts_as" {
  for_each           = toset(["rag-api", "rag-ingest", "rag-build"])
  service_account_id = google_service_account.workload[each.value].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.sa["rag-ci-deploy"]}"
}

# The human operator can act as build SA (gcloud builds submit) and mint tokens for eval SAs.
resource "google_service_account_iam_member" "admin_acts_as_build" {
  service_account_id = google_service_account.workload["rag-build"].name
  role               = "roles/iam.serviceAccountUser"
  member             = "user:${var.admin_email}"
}

resource "google_service_account_iam_member" "admin_impersonates_eval" {
  for_each           = google_service_account.eval
  service_account_id = each.value.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "user:${var.admin_email}"
}
