variable "project_id" {
  description = "GCP project that hosts the platform."
  type        = string
}

variable "region" {
  description = "Primary region. All regional data services live here (EU data residency)."
  type        = string
  default     = "europe-west1"
}

variable "github_repo" {
  description = "owner/name of the GitHub repo allowed to federate into GCP."
  type        = string
  default     = "soodrajesh/gcp-enterprise-rag-platform"
}

variable "billing_account_id" {
  description = "Billing account ID for the budget guardrail."
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget in the billing account's currency; alerts fire at 25/50/90/100%."
  type        = number
  default     = 20
}

variable "alert_email" {
  description = "Recipient for SLO burn-rate, budget and guardrail alerts."
  type        = string
}

variable "admin_email" {
  description = "Human operator: granted invoker on the API and confidential clearance."
  type        = string
}

variable "api_image" {
  description = "Full image reference for the API service. Defaults to a placeholder so the platform can be created before the first build."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "ingest_image" {
  description = "Full image reference for the ingest service."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "resource_suffix" {
  description = "Appended to names that GCP refuses to reuse after deletion (KMS key ring, WIF pool: 30-day soft-delete). scripts/up.sh generates one per deployment so rebuilds never collide."
  type        = string
  default     = ""
}

variable "enforce_org_policies" {
  description = "Apply project-level organisation policy constraints (needs roles/orgpolicy.policyAdmin)."
  type        = bool
  default     = true
}
