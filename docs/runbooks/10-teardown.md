# 10 · Teardown

**When:** done with the demo; stop all spend. The platform is 100 % Terraform, so teardown is one command.

```bash
./scripts/down.sh            # terraform destroy + post-checks (buckets force_destroy; BigQuery deletes contents)
./scripts/down.sh --purge    # ...and delete the Terraform state bucket too: nothing of this repo remains
```
Things to know:
* **KMS keys are not deleted immediately** — key versions are scheduled for destruction (default 30 days) and the key ring name stays reserved. A destroyed key ring / WIF pool name cannot be reused for 30 days. `up.sh` handles this: each fresh deployment gets a unique `resource_suffix` (stored in the gitignored `.deploy-suffix`, removed by `down.sh`), so rebuilds never collide.
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
