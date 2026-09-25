variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "image" { type = string }
variable "service_account_email" { type = string }
variable "ingress" {
  type    = string
  default = "INGRESS_TRAFFIC_ALL"
}
variable "env" {
  type    = map(string)
  default = {}
}
variable "cpu" {
  type    = string
  default = "1"
}
variable "memory" {
  type    = string
  default = "1Gi"
}
variable "min_instances" {
  type    = number
  default = 0
}
variable "max_instances" {
  type    = number
  default = 3
}
variable "concurrency" {
  type    = number
  default = 20
}
variable "timeout_seconds" {
  type    = number
  default = 120
}
variable "network" { type = string }
variable "subnetwork" { type = string }
variable "invoker_members" {
  description = "IAM members allowed to call the service (roles/run.invoker). Never allUsers."
  type        = list(string)
  default     = []
}
variable "labels" {
  type    = map(string)
  default = {}
}

resource "google_cloud_run_v2_service" "this" {
  project             = var.project_id
  name                = var.name
  location            = var.region
  ingress             = var.ingress
  deletion_protection = false
  labels              = var.labels

  template {
    service_account                  = var.service_account_email
    timeout                          = "${var.timeout_seconds}s"
    max_instance_request_concurrency = var.concurrency

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # Direct VPC egress (no serverless connector to run/patch/pay for). ALL_TRAFFIC sends
    # everything through the VPC, where the firewall permits only the restricted Google VIP.
    vpc_access {
      egress = "ALL_TRAFFIC"
      network_interfaces {
        network    = var.network
        subnetwork = var.subnetwork
      }
    }

    containers {
      image = var.image

      resources {
        limits            = { cpu = var.cpu, memory = var.memory }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }

      startup_probe {
        http_get { path = "/healthz" }
        initial_delay_seconds = 0
        period_seconds        = 3
        failure_threshold     = 10
      }
    }
  }

  # Image is rolled by CI (gcloud run deploy / terraform var), don't fight it.
  lifecycle {
    ignore_changes = [client, client_version]
  }
}

resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = toset(var.invoker_members)
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = each.value
}

output "name" { value = google_cloud_run_v2_service.this.name }
output "uri" { value = google_cloud_run_v2_service.this.uri }
