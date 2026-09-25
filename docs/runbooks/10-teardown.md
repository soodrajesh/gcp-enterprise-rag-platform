# 10 · Teardown

**When:** done with the demo; stop all spend. The platform is 100 % Terraform, so teardown is one command.

```bash
make destroy          # terraform destroy (buckets use force_destroy; BigQuery deletes contents)
```
Things to know:
* **KMS keys are not deleted immediately** — key versions are scheduled for destruction (default 30 days) and the key ring name stays reserved. A destroyed key ring name cannot be reused, so change `name` in `main.tf`'s `module.kms` (e.g. `rag-eu-2`) before re-applying.
* **Org policies** applied at project level are removed with the project resources; those at folder/org level are not touched.
* The **state bucket** is intentionally *not* managed by Terraform:
  ```bash
  gcloud storage rm -r gs://$PROJECT-tfstate
  ```
* Confirm nothing billable is left:
  ```bash
  gcloud run services list --project $PROJECT
  gcloud storage buckets list --project $PROJECT --format='value(name)'
  bq ls --project_id $PROJECT
  gcloud compute networks list --project $PROJECT
  ```

## Rebuild from scratch
Runbook [01](01-bootstrap-and-deploy.md) — about 15 minutes end to end.
