terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }

  # Bucket is created by scripts/bootstrap.sh (chicken-and-egg: state can't create its own bucket).
  backend "gcs" {
    prefix = "rag-platform"
  }
}
