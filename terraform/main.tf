locals {
  labels = {
    app         = "rag-platform"
    managed_by  = "terraform"
    environment = "demo"
  }
}

# --- Encryption ---------------------------------------------------------------------------
data "google_bigquery_default_service_account" "bq" {
  project    = var.project_id
  depends_on = [google_project_service.apis]
}

module "kms" {
  source     = "./modules/kms"
  project_id = var.project_id
  region     = var.region
  name       = "rag-eu${var.resource_suffix}"
  encrypter_members = {
    gcs      = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
    bigquery = "serviceAccount:${data.google_bigquery_default_service_account.bq.email}"
  }
  depends_on = [google_project_service.apis]
}

# --- Network ------------------------------------------------------------------------------
module "network" {
  source     = "./modules/network"
  project_id = var.project_id
  region     = var.region
  name       = "rag-vpc"
  depends_on = [google_project_service.apis]
}

# --- Data plane ---------------------------------------------------------------------------
module "data" {
  source           = "./modules/data_platform"
  project_id       = var.project_id
  region           = var.region
  kms_key_id       = module.kms.key_id
  docs_bucket_name = "${var.project_id}-rag-docs"
  depends_on       = [google_project_service.apis]
}

# --- Container registry -------------------------------------------------------------------
resource "google_artifact_registry_repository" "rag" {
  project       = var.project_id
  location      = var.region
  repository_id = "rag"
  format        = "DOCKER"
  description   = "RAG platform images (vulnerability-scanned on push)"

  docker_config { immutable_tags = true }

  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-last-10"
    action = "KEEP"
    most_recent_versions { keep_count = 10 }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition { older_than = "2592000s" }
  }
  depends_on = [google_project_service.apis]
}

resource "google_artifact_registry_repository_iam_member" "runtime_pull" {
  for_each   = toset(["rag-api", "rag-ingest"])
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.rag.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${local.sa[each.value]}"
}

# Staging bucket for `gcloud builds submit` so builds don't depend on the default bucket.
resource "google_storage_bucket" "build_staging" {
  project                     = var.project_id
  name                        = "${var.project_id}-build-staging"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  lifecycle_rule {
    condition { age = 7 }
    action { type = "Delete" }
  }
}

resource "google_storage_bucket_iam_member" "build_reads_source" {
  bucket = google_storage_bucket.build_staging.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${local.sa["rag-build"]}"
}

resource "google_storage_bucket_iam_member" "deployer_stages_source" {
  bucket = google_storage_bucket.build_staging.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.sa["rag-ci-deploy"]}"
}

resource "google_storage_bucket_iam_member" "admin_stages_source" {
  bucket = google_storage_bucket.build_staging.name
  role   = "roles/storage.objectAdmin"
  member = "user:${var.admin_email}"
}

# --- Compute: API (user-facing) and Ingest (event-driven) -----------------------------------
module "api" {
  source                = "./modules/cloud_run_service"
  project_id            = var.project_id
  region                = var.region
  name                  = "rag-api"
  image                 = var.api_image
  service_account_email = local.sa["rag-api"]
  ingress               = "INGRESS_TRAFFIC_ALL" # protected by IAM (no allUsers); see ADR 0006 for the LB+IAP path
  network               = module.network.network
  subnetwork            = module.network.subnetwork
  memory                = "1Gi"
  labels                = local.labels

  env = {
    PROJECT_ID        = var.project_id
    REGION            = var.region
    CLEARANCE_MAP     = jsonencode(local.clearance_map)
    DEFAULT_CLEARANCE = "public"
  }

  invoker_members = concat(
    ["user:${var.admin_email}"],
    [for e in values(local.eval_sa) : "serviceAccount:${e}"],
  )
  depends_on = [google_project_service.apis, google_project_iam_member.workload]
}

module "ingest" {
  source                = "./modules/cloud_run_service"
  project_id            = var.project_id
  region                = var.region
  name                  = "rag-ingest"
  image                 = var.ingest_image
  service_account_email = local.sa["rag-ingest"]
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY" # only Eventarc can reach it
  network               = module.network.network
  subnetwork            = module.network.subnetwork
  memory                = "2Gi"
  cpu                   = "1"
  concurrency           = 4
  timeout_seconds       = 300
  labels                = local.labels

  env = {
    PROJECT_ID = var.project_id
    REGION     = var.region
  }

  invoker_members = ["serviceAccount:${local.sa["rag-eventarc"]}"]
  depends_on      = [google_project_service.apis, google_project_iam_member.workload]
}

# --- Event wiring: object finalized in the docs bucket -> ingest ------------------------------
resource "google_eventarc_trigger" "docs_finalized" {
  project  = var.project_id
  name     = "rag-docs-finalized"
  location = var.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = module.data.docs_bucket
  }

  destination {
    cloud_run_service {
      service = module.ingest.name
      region  = var.region
      path    = "/"
    }
  }
  service_account = local.sa["rag-eventarc"]
  labels          = local.labels

  depends_on = [
    google_project_iam_member.gcs_pubsub_publisher,
    google_project_iam_member.workload,
  ]
}

# --- Observability & cost guardrails ---------------------------------------------------------
module "observability" {
  source       = "./modules/observability"
  project_id   = var.project_id
  service_name = module.api.name
  alert_email  = var.alert_email
  depends_on   = [google_project_service.apis]
}

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account_id
  display_name    = "rag-platform monthly guardrail"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }
  amount {
    specified_amount {
      units = tostring(var.budget_amount)
    }
  }
  dynamic "threshold_rules" {
    for_each = [0.25, 0.5, 0.9, 1.0]
    content { threshold_percent = threshold_rules.value }
  }
  all_updates_rule {
    monitoring_notification_channels = [module.observability.notification_channel]
    disable_default_iam_recipients   = false
  }
}

# --- Keyless CI/CD ---------------------------------------------------------------------------
module "github_wif" {
  source          = "./modules/github_wif"
  project_id      = var.project_id
  github_repo     = var.github_repo
  plan_sa_email   = local.sa["rag-ci-plan"]
  deploy_sa_email = local.sa["rag-ci-deploy"]
  pool_suffix     = var.resource_suffix
  depends_on      = [google_project_service.apis]
}
