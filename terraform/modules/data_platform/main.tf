variable "project_id" { type = string }
variable "region" { type = string }
variable "kms_key_id" { type = string }
variable "docs_bucket_name" { type = string }
variable "embedding_dim" {
  type    = number
  default = 768
}

# --- Document landing zone ---------------------------------------------------
resource "google_storage_bucket" "docs" {
  project                     = var.project_id
  name                        = var.docs_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true # demo teardown

  versioning { enabled = true }

  encryption { default_kms_key_name = var.kms_key_id }

  lifecycle_rule {
    condition {
      num_newer_versions = 5
      with_state         = "ARCHIVED"
    }
    action { type = "Delete" }
  }

  soft_delete_policy { retention_duration_seconds = 604800 }
}

# --- Vector store + audit log ------------------------------------------------
resource "google_bigquery_dataset" "rag" {
  project                    = var.project_id
  dataset_id                 = "rag"
  location                   = var.region
  description                = "RAG chunks (vectors) and query audit log. CMEK-encrypted."
  delete_contents_on_destroy = true

  default_encryption_configuration { kms_key_name = var.kms_key_id }
  labels = { data_classification = "mixed", owner = "platform" }
}

resource "google_bigquery_table" "chunks" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.rag.dataset_id
  table_id            = "chunks"
  deletion_protection = false

  encryption_configuration { kms_key_name = var.kms_key_id }
  description = "One row per document chunk with its embedding and classification."

  schema = jsonencode([
    { name = "chunk_id", type = "STRING", mode = "REQUIRED" },
    { name = "doc_uri", type = "STRING", mode = "REQUIRED" },
    { name = "doc_title", type = "STRING", mode = "NULLABLE" },
    { name = "doc_generation", type = "INT64", mode = "NULLABLE" },
    { name = "classification", type = "STRING", mode = "REQUIRED" },
    { name = "chunk_index", type = "INT64", mode = "NULLABLE" },
    { name = "heading", type = "STRING", mode = "NULLABLE" },
    { name = "content", type = "STRING", mode = "REQUIRED" },
    { name = "embedding", type = "FLOAT64", mode = "REPEATED" },
    { name = "redactions", type = "INT64", mode = "NULLABLE" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "NULLABLE" },
  ])

  clustering = ["classification", "doc_uri"]
}

resource "google_bigquery_table" "query_log" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.rag.dataset_id
  table_id            = "query_log"
  deletion_protection = false

  encryption_configuration { kms_key_name = var.kms_key_id }
  description = "Append-only audit trail: who asked what, what was retrieved, cost and latency."

  time_partitioning {
    type          = "DAY"
    field         = "ts"
    expiration_ms = 34560000000 # 400 days, matches the audit-log retention policy
  }

  schema = jsonencode([
    { name = "request_id", type = "STRING", mode = "REQUIRED" },
    { name = "ts", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "caller_hash", type = "STRING", mode = "NULLABLE" },
    { name = "clearance", type = "STRING", mode = "NULLABLE" },
    { name = "question", type = "STRING", mode = "NULLABLE" },
    { name = "outcome", type = "STRING", mode = "NULLABLE" },
    { name = "hits", type = "INT64", mode = "NULLABLE" },
    { name = "cited_docs", type = "STRING", mode = "REPEATED" },
    { name = "prompt_tokens", type = "INT64", mode = "NULLABLE" },
    { name = "output_tokens", type = "INT64", mode = "NULLABLE" },
    { name = "total_ms", type = "INT64", mode = "NULLABLE" },
    { name = "embed_ms", type = "INT64", mode = "NULLABLE" },
    { name = "search_ms", type = "INT64", mode = "NULLABLE" },
    { name = "generate_ms", type = "INT64", mode = "NULLABLE" },
  ])
}

# Operator-facing view: daily volume, outcome mix, latency percentiles, token spend.
resource "google_bigquery_table" "daily_summary" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.rag.dataset_id
  table_id            = "v_daily_summary"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT
        DATE(ts) AS day,
        COUNT(*) AS requests,
        COUNTIF(outcome = 'answered') AS answered,
        COUNTIF(STARTS_WITH(outcome, 'blocked')) AS blocked,
        COUNTIF(outcome IN ('unanswerable', 'no_relevant_context')) AS no_answer,
        APPROX_QUANTILES(total_ms, 100)[OFFSET(50)] AS p50_ms,
        APPROX_QUANTILES(total_ms, 100)[OFFSET(95)] AS p95_ms,
        SUM(prompt_tokens) AS prompt_tokens,
        SUM(output_tokens) AS output_tokens
      FROM `${var.project_id}.${google_bigquery_dataset.rag.dataset_id}.${google_bigquery_table.query_log.table_id}`
      GROUP BY day
    SQL
  }
}

output "docs_bucket" { value = google_storage_bucket.docs.name }
output "dataset_id" { value = google_bigquery_dataset.rag.dataset_id }
output "chunks_table_id" { value = google_bigquery_table.chunks.table_id }
output "query_log_table_id" { value = google_bigquery_table.query_log.table_id }
