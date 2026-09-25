# Preventive guardrails enforced by the platform itself, not by convention.
# Project-scoped here; in a real landing zone these sit on a folder (see docs/adr/0007).
locals {
  boolean_constraints = var.enforce_org_policies ? [
    "iam.disableServiceAccountKeyCreation", # no long-lived SA keys, ever
    "iam.disableServiceAccountKeyUpload",
    "storage.uniformBucketLevelAccess", # no per-object ACL surprises
    "storage.publicAccessPrevention",   # buckets can never be made public
    "run.requireInvokerIam",            # Cloud Run must use IAM, no allUsers
    "compute.skipDefaultNetworkCreation",
  ] : []
}

resource "google_org_policy_policy" "boolean" {
  for_each = toset(local.boolean_constraints)
  name     = "projects/${var.project_id}/policies/${each.value}"
  parent   = "projects/${var.project_id}"

  spec {
    rules { enforce = "TRUE" }
  }
  depends_on = [google_project_service.apis]
}
