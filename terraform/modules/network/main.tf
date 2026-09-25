variable "project_id" { type = string }
variable "region" { type = string }
variable "name" { type = string }
variable "cidr" {
  type    = string
  default = "10.10.0.0/24"
}

resource "google_compute_network" "vpc" {
  project                 = var.project_id
  name                    = var.name
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "run" {
  project                  = var.project_id
  name                     = "${var.name}-run"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = var.cidr
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# --- Egress lock-down -------------------------------------------------------
# Workloads may talk to Google APIs through the *restricted* VIP and nothing else.
# There is no route or NAT to the public internet, so a compromised container (or a
# prompt-injected model with a tool) has nowhere to exfiltrate to.
resource "google_compute_firewall" "allow_restricted_vip" {
  project   = var.project_id
  name      = "${var.name}-egress-allow-restricted-vip"
  network   = google_compute_network.vpc.name
  direction = "EGRESS"
  priority  = 900

  destination_ranges = ["199.36.153.4/30"]
  allow {
    protocol = "tcp"
    ports    = ["443"]
  }
  log_config { metadata = "INCLUDE_ALL_METADATA" }
}

resource "google_compute_firewall" "deny_all_egress" {
  project   = var.project_id
  name      = "${var.name}-egress-deny-all"
  network   = google_compute_network.vpc.name
  direction = "EGRESS"
  priority  = 1000

  destination_ranges = ["0.0.0.0/0"]
  deny { protocol = "all" }
  log_config { metadata = "INCLUDE_ALL_METADATA" }
}

# Private DNS: every *.googleapis.com name resolves to the restricted VIP.
resource "google_dns_managed_zone" "googleapis" {
  project    = var.project_id
  name       = "${var.name}-googleapis"
  dns_name   = "googleapis.com."
  visibility = "private"

  private_visibility_config {
    networks { network_url = google_compute_network.vpc.id }
  }
}

resource "google_dns_record_set" "restricted_a" {
  project      = var.project_id
  managed_zone = google_dns_managed_zone.googleapis.name
  name         = "restricted.googleapis.com."
  type         = "A"
  ttl          = 300
  rrdatas      = ["199.36.153.4", "199.36.153.5", "199.36.153.6", "199.36.153.7"]
}

resource "google_dns_record_set" "wildcard_cname" {
  project      = var.project_id
  managed_zone = google_dns_managed_zone.googleapis.name
  name         = "*.googleapis.com."
  type         = "CNAME"
  ttl          = 300
  rrdatas      = ["restricted.googleapis.com."]
}

output "network" { value = google_compute_network.vpc.name }
output "subnetwork" { value = google_compute_subnetwork.run.name }
