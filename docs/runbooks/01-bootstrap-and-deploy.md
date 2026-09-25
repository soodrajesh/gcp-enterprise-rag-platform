# 01 · Bootstrap & first deploy

**When:** new project, or rebuilding after teardown. ~15 min.

**The one-command path:** `./scripts/up.sh` performs every step below (idempotent; `--plan` previews). The manual steps are documented so you can see what it does and debug it.

**Prereqs:** `gcloud`, `terraform >= 1.9`, a project with billing, and — for the org-policy guardrails — `roles/orgpolicy.policyAdmin` on the org.

## 1. Grant org-policy admin (one-time; Organization Admin does *not* include it)
```bash
gcloud organizations add-iam-policy-binding <ORG_ID> \
  --member="user:you@example.com" --role="roles/orgpolicy.policyAdmin"
```
```
Updated IAM policy for organization [<ORG_ID>].
bindings:
- members:
  - user:operator@example.com
  role: roles/orgpolicy.policyAdmin
```

## 2. Pre-create the Eventarc service agent
Avoids the `Permission denied while using the Eventarc Service Agent` race (see [09](09-troubleshooting.md#t1)).
```bash
gcloud beta services identity create --service=eventarc.googleapis.com --project $PROJECT
```
```
Service identity created: service-273040233392@gcp-sa-eventarc.iam.gserviceaccount.com
```

## 3. State bucket + Terraform
```bash
./scripts/bootstrap.sh $PROJECT $REGION
cp terraform/example.tfvars terraform/terraform.tfvars   # edit values
make init && make plan && make apply
```
```
state bucket: gs://claude-code-507112-tfstate
...
Apply complete! Resources: 6 added, 1 changed, 2 destroyed.   # final converging run
Outputs:
api_url        = "https://rag-api-mumqq56yxq-ew.a.run.app"
artifact_repo  = "europe-west1-docker.pkg.dev/claude-code-507112/rag"
docs_bucket    = "claude-code-507112-rag-docs"
```
```bash
terraform -chdir=terraform state list | wc -l
```
```
121
```

## 4. Build and roll the images
Terraform ships a placeholder `hello` image so the platform can exist before the first build.
```bash
make images TAG=v1     # Cloud Build, dedicated SA, SLSA provenance
make deploy TAG=v1
```
```
ID                                    DURATION  IMAGES                                                               STATUS
8075d08b-12aa-4cc6-b497-faf43c79ee4f  46S       europe-west1-docker.pkg.dev/claude-code-507112/rag/api:v1 (+1 more)  SUCCESS
Service [rag-api] revision [rag-api-00002-hb6] has been deployed and is serving 100 percent of traffic.
```

## 5. Seed and evaluate
```bash
make seed && make eval
```
Success = `11/11 passed` (see [03](03-query-and-access-control.md)).

## If it goes wrong
See [09 Troubleshooting](09-troubleshooting.md) — every error above that you might hit is catalogued there.
