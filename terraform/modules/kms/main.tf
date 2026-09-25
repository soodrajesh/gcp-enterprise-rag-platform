variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }

variable "encrypter_members" {
  description = "Service agents allowed to use the key, keyed by a static label (GCS, BigQuery)."
  type        = map(string)
}

resource "google_kms_key_ring" "this" {
  project  = var.project_id
  name     = var.name
  location = var.region
}

resource "google_kms_crypto_key" "data" {
  name            = "data"
  key_ring        = google_kms_key_ring.this.id
  rotation_period = "7776000s" # 90 days
  purpose         = "ENCRYPT_DECRYPT"

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  # Demo project: teardown must be possible. Flip to true in a real environment.
  lifecycle { prevent_destroy = false }
}

resource "google_kms_crypto_key_iam_member" "use" {
  for_each      = var.encrypter_members
  crypto_key_id = google_kms_crypto_key.data.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = each.value
}

output "key_id" {
  value      = google_kms_crypto_key.data.id
  depends_on = [google_kms_crypto_key_iam_member.use]
}
