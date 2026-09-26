variable "project_id" { type = string }
variable "github_repo" { type = string }
variable "plan_sa_email" { type = string }
variable "deploy_sa_email" { type = string }
variable "pool_suffix" {
  description = "Pool IDs are soft-deleted for 30 days and cannot be reused; suffix per deployment."
  type        = string
  default     = ""
}
variable "deploy_environment" {
  description = "GitHub Actions environment the deploy identity is bound to (add required reviewers in repo settings)."
  type        = string
  default     = "prod"
}

# Keyless auth: GitHub's OIDC token is exchanged for short-lived GCP credentials.
# No service account keys exist anywhere (and org policy forbids creating them).
resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github${var.pool_suffix}"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"        = "assertion.sub"
    "attribute.repository"  = "assertion.repository"
    "attribute.environment" = "assertion.environment"
    "attribute.ref"         = "assertion.ref"
  }
  # Hard gate: tokens from any other repo are rejected before any IAM check.
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

# Read-only plan identity: any workflow in this repo (PRs included).
resource "google_service_account_iam_member" "plan" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.plan_sa_email}"
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

# Deploy identity: only jobs bound to the protected GitHub environment can assume it.
# Bound on the *environment attribute*, not a literal `repo:<owner>/<repo>:environment:<env>` subject:
# GitHub now issues IMMUTABLE subject claims for new repos (`repo:<owner>@<id>/<repo>@<id>:...`), which
# a name-based subject binding silently never matches. The repository restriction is enforced by the
# provider's attribute_condition, so the two together are equivalent and format-independent.
resource "google_service_account_iam_member" "deploy" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.deploy_sa_email}"
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.environment/${var.deploy_environment}"
}

output "provider" { value = google_iam_workload_identity_pool_provider.github.name }
