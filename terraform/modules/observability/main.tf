variable "project_id" { type = string }
variable "service_name" { type = string }
variable "alert_email" { type = string }

locals {
  run_filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.service_name}\""
}

# --- Log-based metrics: turn structured "ask" log lines into time series -----------------
resource "google_logging_metric" "ask_outcomes" {
  project = var.project_id
  name    = "rag_ask_outcomes"
  filter  = "${local.run_filter} AND jsonPayload.message=\"ask\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "outcome"
      value_type  = "STRING"
      description = "answered | unanswerable | no_relevant_context | blocked:<reason>"
    }
  }
  label_extractors = { "outcome" = "EXTRACT(jsonPayload.outcome)" }
}

resource "google_logging_metric" "ask_latency" {
  project = var.project_id
  name    = "rag_ask_latency_ms"
  filter  = "${local.run_filter} AND jsonPayload.message=\"ask\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "ms"
  }
  value_extractor = "EXTRACT(jsonPayload.total_ms)"
  bucket_options {
    exponential_buckets {
      num_finite_buckets = 20
      growth_factor      = 1.5
      scale              = 50
    }
  }
}

# --- Notification channel ----------------------------------------------------------------
resource "google_monitoring_notification_channel" "email" {
  project      = var.project_id
  display_name = "Platform on-call (email)"
  type         = "email"
  labels       = { email_address = var.alert_email }
}

# --- SLOs ------------------------------------------------------------------------------
resource "google_monitoring_custom_service" "api" {
  project      = var.project_id
  service_id   = "rag-api"
  display_name = "RAG API"
}

resource "google_monitoring_slo" "availability" {
  project             = var.project_id
  service             = google_monitoring_custom_service.api.service_id
  slo_id              = "availability-99-5"
  display_name        = "99.5% of requests are not 5xx (28d)"
  goal                = 0.995
  rolling_period_days = 28

  request_based_sli {
    good_total_ratio {
      total_service_filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"${var.service_name}\""
      bad_service_filter   = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"${var.service_name}\" metric.label.\"response_code_class\"=\"5xx\""
    }
  }
}

resource "google_monitoring_slo" "latency" {
  project             = var.project_id
  service             = google_monitoring_custom_service.api.service_id
  slo_id              = "latency-p95-10s"
  display_name        = "95% of requests complete in under 10s (28d)"
  goal                = 0.95
  rolling_period_days = 28

  request_based_sli {
    distribution_cut {
      distribution_filter = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"${var.service_name}\""
      range {
        max = 10000
      }
    }
  }
}

# --- Alerts: multi-window burn rate (Google SRE workbook) ---------------------------------
resource "google_monitoring_alert_policy" "fast_burn" {
  project      = var.project_id
  display_name = "RAG API - availability fast burn (14.4x / 1h)"
  combiner     = "OR"

  conditions {
    display_name = "Error budget burning 14.4x faster than allowed"
    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.availability.name}\", \"3600s\")"
      comparison      = "COMPARISON_GT"
      threshold_value = 14.4
      duration        = "0s"
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    mime_type = "text/markdown"
    content   = "At this rate the 28-day error budget is gone in ~2 days. Runbook: `docs/runbook.md#availability-burn`."
  }
}

resource "google_monitoring_alert_policy" "slow_burn" {
  project      = var.project_id
  display_name = "RAG API - availability slow burn (3x / 6h)"
  combiner     = "OR"

  conditions {
    display_name = "Error budget burning 3x faster than allowed"
    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.availability.name}\", \"21600s\")"
      comparison      = "COMPARISON_GT"
      threshold_value = 3
      duration        = "0s"
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
}

resource "google_monitoring_alert_policy" "guardrail_spike" {
  project      = var.project_id
  display_name = "RAG API - prompt-injection attempts spiking"
  combiner     = "OR"

  conditions {
    display_name = ">10 blocked requests in 5 minutes"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ask_outcomes.name}\" AND resource.type=\"cloud_run_revision\" AND metric.label.\"outcome\"=monitoring.regex.full_match(\"blocked:.*\")"
      comparison      = "COMPARISON_GT"
      threshold_value = 10
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
  documentation {
    mime_type = "text/markdown"
    content   = "Someone is probing the assistant. Check `rag.query_log` for the caller_hash and outcome `blocked:*`."
  }
}

# --- Dashboard ------------------------------------------------------------------------------
locals {
  req_filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"${var.service_name}\""
  lat_filter = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"${var.service_name}\""
}

resource "google_monitoring_dashboard" "rag" {
  project = var.project_id
  dashboard_json = jsonencode({
    displayName = "RAG Platform - Service Health"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          xPos = 0, yPos = 0, width = 6, height = 4
          widget = {
            title = "Requests / s by response class"
            xyChart = {
              dataSets = [{
                plotType = "STACKED_AREA"
                timeSeriesQuery = { timeSeriesFilter = {
                  filter      = local.req_filter
                  aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["metric.label.response_code_class"] }
                } }
              }]
            }
          }
        },
        {
          xPos = 6, yPos = 0, width = 6, height = 4
          widget = {
            title = "Request latency (Cloud Run) p50 / p95 / p99"
            xyChart = {
              dataSets = [for p in ["50", "95", "99"] : {
                plotType       = "LINE"
                legendTemplate = "p${p}"
                timeSeriesQuery = { timeSeriesFilter = {
                  filter      = local.lat_filter
                  aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_${p}", crossSeriesReducer = "REDUCE_MEAN" }
                } }
              }]
            }
          }
        },
        {
          xPos = 0, yPos = 4, width = 6, height = 4
          widget = {
            title = "RAG outcomes / min (answered vs guardrail vs no-answer)"
            xyChart = {
              dataSets = [{
                plotType = "STACKED_BAR"
                timeSeriesQuery = { timeSeriesFilter = {
                  filter      = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ask_outcomes.name}\" resource.type=\"cloud_run_revision\""
                  aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_SUM", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["metric.label.outcome"] }
                } }
              }]
            }
          }
        },
        {
          xPos = 6, yPos = 4, width = 6, height = 4
          widget = {
            title = "End-to-end ask latency p50 / p95 (ms, from structured logs)"
            xyChart = {
              dataSets = [for p in ["50", "95"] : {
                plotType       = "LINE"
                legendTemplate = "p${p}"
                timeSeriesQuery = { timeSeriesFilter = {
                  filter      = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ask_latency.name}\" resource.type=\"cloud_run_revision\""
                  aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_${p}", crossSeriesReducer = "REDUCE_MEAN" }
                } }
              }]
            }
          }
        },
        {
          xPos = 0, yPos = 8, width = 12, height = 4
          widget = {
            title = "Container instances"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = { timeSeriesFilter = {
                  filter      = "metric.type=\"run.googleapis.com/container/instance_count\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"${var.service_name}\""
                  aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["metric.label.state"] }
                } }
              }]
            }
          }
        },
      ]
    }
  })
}

output "slo_availability" { value = google_monitoring_slo.availability.name }
output "dashboard_id" { value = google_monitoring_dashboard.rag.id }
output "notification_channel" { value = google_monitoring_notification_channel.email.id }
