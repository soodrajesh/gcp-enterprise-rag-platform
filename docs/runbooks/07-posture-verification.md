# 07 · Posture verification — prove the guardrails are actually on

**When:** before a review/audit, after any Terraform change, quarterly. Each check states what "good" looks like.

## 1. Preventive org policies
```bash
gcloud org-policies list --project $PROJECT
```
```
CONSTRAINT                            LIST_POLICY  BOOLEAN_POLICY  ETAG
iam.disableServiceAccountKeyCreation  -            SET             CKma29UGEODj44UB-
storage.uniformBucketLevelAccess      -            SET             CKma29UGELjc0YQB-
run.managed.requireInvokerIam         -            SET             CKKb29UGELjE9qEC-
compute.skipDefaultNetworkCreation    -            SET             CKma29UGEODp54MB-
storage.publicAccessPrevention        -            SET             CKma29UGEIDo8oMB-
iam.disableServiceAccountKeyUpload    -            SET             CKma29UGELjXo4YB-
```

## 2. Encryption: CMEK with rotation
```bash
gcloud kms keys describe data --keyring rag-eu --location $REGION --project $PROJECT \
  --format='yaml(name,purpose,rotationPeriod,nextRotationTime,primary.state,primary.protectionLevel)'
```
```
name: projects/claude-code-507112/locations/europe-west1/keyRings/rag-eu/cryptoKeys/data
nextRotationTime: '2026-12-24T19:30:56.405919Z'
primary: {protectionLevel: SOFTWARE, state: ENABLED}
purpose: ENCRYPT_DECRYPT
rotationPeriod: 7776000s
```
```bash
gcloud storage buckets describe gs://$PROJECT-rag-docs \
  --format='yaml(location,uniform_bucket_level_access,public_access_prevention,default_kms_key,versioning_enabled)'
```
```
default_kms_key: projects/claude-code-507112/locations/europe-west1/keyRings/rag-eu/cryptoKeys/data
location: EUROPE-WEST1
public_access_prevention: enforced
uniform_bucket_level_access: true
versioning_enabled: true
```

## 3. Nobody but named identities can call the API (no `allUsers`)
```bash
gcloud run services get-iam-policy rag-api --region $REGION --project $PROJECT
```
```
bindings:
- members:
  - serviceAccount:rag-eval-confidential@claude-code-507112.iam.gserviceaccount.com
  - serviceAccount:rag-eval-internal@claude-code-507112.iam.gserviceaccount.com
  - serviceAccount:rag-eval-public@claude-code-507112.iam.gserviceaccount.com
  - user:rajeshsoodit@gmail.com
  role: roles/run.invoker
```
Ingest is unreachable from the internet:
```bash
gcloud run services describe rag-ingest --region $REGION --project $PROJECT \
  --format='value(metadata.annotations."run.googleapis.com/ingress")'
```
```
internal
```
Event wiring:
```bash
gcloud eventarc triggers list --location $REGION --project $PROJECT
```
```
NAME                VALUE                        SERVICE     SERVICE_ACCOUNT
rag-docs-finalized  claude-code-507112-rag-docs  rag-ingest  rag-eventarc@claude-code-507112.iam.gserviceaccount.com
```

## 4. Network egress is locked down — *runtime proof*
Firewall intent:
```bash
gcloud compute firewall-rules list --project $PROJECT --filter="name~rag-vpc" \
  --format='table(name,direction,priority,destinationRanges.list(),allowed[].map().firewall_rule().list(),denied[].map().firewall_rule().list())'
```
```
NAME                                 DIRECTION  PRIORITY  DESTINATION_RANGES  ALLOW    DENY
rag-vpc-egress-allow-restricted-vip  EGRESS     900       199.36.153.4/30     tcp:443
rag-vpc-egress-deny-all              EGRESS     1000      0.0.0.0/0                    all
```
Actual behaviour — a throw-away Cloud Run Job in the same VPC/egress config (same SA as ingest):
```bash
gcloud run jobs create egress-probe --project $PROJECT --region $REGION \
  --image $REGION-docker.pkg.dev/$PROJECT/rag/ingest:v3 \
  --service-account rag-ingest@$PROJECT.iam.gserviceaccount.com \
  --network rag-vpc --subnet rag-vpc-run --vpc-egress all-traffic \
  --command python --args="^@^-c@<python that resolves + fetches, see below>" --max-retries 0
gcloud run jobs execute egress-probe --region $REGION --project $PROJECT --wait
```
```
dns storage.googleapis.com -> 199.36.153.4
https://example.com -> BLOCKED: URLError <urlopen error [Errno 101] Network is unreachable>
https://storage.googleapis.com/storage/v1/b/none -> reachable, HTTP 401
```
Reading: `*.googleapis.com` resolves to the **restricted VIP**, the public internet is **unreachable**, and Google APIs still work (401 = the API answered; no credentials were sent). Clean up: `gcloud run jobs delete egress-probe --region $REGION --quiet`.

> gcloud tip: the `^@^` prefix changes the argument delimiter so commas inside the Python don't split the argument list.

## 5. Least privilege: who can touch the vectors?
Project-level roles for the API identity (note: no `storage.*`, no BigQuery data roles at project level):
```bash
gcloud projects get-iam-policy $PROJECT --flatten=bindings --filter="bindings.members:rag-api@" --format='value(bindings.role)'
```
```
roles/aiplatform.user
roles/bigquery.jobUser
roles/cloudtrace.agent
roles/dlp.user
roles/logging.logWriter
roles/monitoring.metricWriter
```
Table-level grants (the data access lives here, not at project level):
```bash
for t in chunks query_log; do echo "== rag.$t"; bq get-iam-policy --table ${PROJECT}:rag.$t \
  | python3 -c "import sys,json;[print(b['role'],[m for m in b['members'] if 'rag-' in m]) for b in json.load(sys.stdin)['bindings']]"; done
```
```
== rag.chunks
roles/bigquery.dataEditor ['serviceAccount:rag-ingest@claude-code-507112.iam.gserviceaccount.com']
roles/bigquery.dataViewer ['serviceAccount:rag-api@claude-code-507112.iam.gserviceaccount.com']
== rag.query_log
roles/bigquery.dataEditor ['serviceAccount:rag-api@claude-code-507112.iam.gserviceaccount.com']
```
Reading: only `rag-ingest` can write vectors; `rag-api` can read them but not modify, and can only *append* to the audit log. (zsh gotcha: write `${PROJECT}:rag.chunks` — `$PROJECT:rag` is parsed as a `:r` modifier.)

## 6. Supply chain
```bash
gcloud artifacts docker images list $REGION-docker.pkg.dev/$PROJECT/rag --include-tags \
  --format='table(package.basename(),tags,createTime.date())'
```
```
IMAGE   TAGS  CREATE_TIME
api     v3    2026-09-25T19:46:30
...
```
Tags are immutable (`docker_config.immutable_tags`), images are built by Cloud Build with `requestedVerifyOption: VERIFIED` (SLSA provenance), and CI runs Trivy + Checkov. Vulnerability findings appear in Console → Artifact Registry → image → *Vulnerabilities* (Container Scanning API enabled by Terraform).

## 7. No service-account keys exist
```bash
for sa in $(gcloud iam service-accounts list --project $PROJECT --format='value(email)'); do
  echo "$sa: $(gcloud iam service-accounts keys list --iam-account $sa --managed-by=user --format='value(name)' | wc -l | tr -d ' ') user-managed keys"; done
```
```
rag-api@claude-code-507112.iam.gserviceaccount.com: 0
rag-ingest@claude-code-507112.iam.gserviceaccount.com: 0
rag-eventarc@claude-code-507112.iam.gserviceaccount.com: 0
rag-build@claude-code-507112.iam.gserviceaccount.com: 0
rag-ci-plan@claude-code-507112.iam.gserviceaccount.com: 0
rag-ci-deploy@claude-code-507112.iam.gserviceaccount.com: 0
rag-eval-{public,internal,confidential}@claude-code-507112.iam.gserviceaccount.com: 0
... (every account in the project, including pre-existing ones: 0)
```
Creation and upload are also blocked by org policy, so this stays true.
