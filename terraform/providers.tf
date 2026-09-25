provider "google" {
  project = var.project_id
  region  = var.region

  # Budgets and some org-level APIs bill/quote against a project, not the caller.
  user_project_override = true
  billing_project       = var.project_id
}
