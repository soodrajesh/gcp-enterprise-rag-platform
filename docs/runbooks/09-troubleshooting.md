# 09 · Troubleshooting catalogue

Every entry below is a **real failure hit while building and deploying this platform** — exact symptom, cause, fix.

<a id="t1"></a>
## T1 · Eventarc trigger: `Permission denied while using the Eventarc Service Agent`
```
Error creating Trigger: googleapi: Error 400: Invalid resource state for "": Permission denied while using
the Eventarc Service Agent. If you recently started to use Eventarc, it may take a few minutes before all
necessary permissions are propagated to the Service Agent.
```
**Cause:** first use of Eventarc in the project; the service agent's role grants haven't propagated.
**Fix:** create the agent first, wait a minute, re-apply.
```bash
gcloud beta services identity create --service=eventarc.googleapis.com --project $PROJECT
# Service identity created: service-273040233392@gcp-sa-eventarc.iam.gserviceaccount.com
terraform apply   # converges
```

<a id="t2"></a>
## T2 · Org policy: `orgpolicy.policies.create denied` (403)
```
Error creating Policy: googleapi: Error 403: Permission 'orgpolicy.policies.create' denied on resource
'//cloudresourcemanager.googleapis.com/projects/claude-code-507112'
```
**Cause:** *Organization Administrator does not include Org Policy admin.*
**Fix:**
```bash
gcloud organizations add-iam-policy-binding <ORG_ID> --member="user:you@example.com" --role="roles/orgpolicy.policyAdmin"
```
(or `-var enforce_org_policies=false` to skip guardrails).

<a id="t3"></a>
## T3 · Org policy: `Error 404: Requested entity was not found`
**Cause:** wrong constraint name — I used `run.requireInvokerIam`; the real constraint is **`run.managed.requireInvokerIam`**.
**Fix:** correct the name. Discover the real names via the Org Policy API (there is no `gcloud` list command for built-in constraints):
```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "x-goog-user-project: $PROJECT" \
  "https://orgpolicy.googleapis.com/v2/projects/$PROJECT/constraints?pageSize=1000" \
  | python3 -c "import sys,json;[print(c['name'].split('/')[-1]) for c in json.load(sys.stdin)['constraints'] if c['name'].split('/')[-1].startswith('run.')]"
```
```
run.allowedIngress
run.allowedVPCEgress
run.allowedBinaryAuthorizationPolicies
run.managed.disableEphemeralDisk
run.managed.disableInlinedSource
run.managed.disableJobsEphemeralDisk
run.managed.disableWorkerPoolsEphemeralDisk
run.managed.requireInvokerIam
```

<a id="t4"></a>
## T4 · Ingest: `Permission bigquery.tables.create denied on dataset`
```
google.api_core.exceptions.Forbidden: 403 POST .../jobs?uploadType=multipart: Access Denied:
Dataset claude-code-507112:rag: Permission bigquery.tables.create denied on dataset claude-code-507112:rag
```
**Cause:** a BigQuery load job defaults to `CREATE_IF_NEEDED`, which requires `tables.create` on the *dataset* even though the table exists. The ingest SA (correctly) only has table-level `dataEditor`.
**Fix:** `LoadJobConfig(create_disposition="CREATE_NEVER")` — keeps least privilege instead of widening the grant.

<a id="t5"></a>
## T5 · Ingest: `AttributeError: Unknown field for SummaryResult: item_count`
**Cause:** the DLP `SummaryResult` field is `count`, not `item_count`.
**Fix:** `sum(r.count for …)`. Lesson: the first end-to-end run against the real API is what finds this; unit tests with mocks would not have.

<a id="t6"></a>
## T6 · Duplicate chunks (a 3-chunk document showing 6)
```
| internal/engineering-handbook.md | internal | 6 |     <- before
| internal/engineering-handbook.md | internal | 3 |     <- after
```
**Cause:** Eventarc is at-least-once, and earlier failed deliveries were retried while new ones ran. Two concurrent invocations both did *delete → load*, so both loads survived.
**Fix:** *load first, then delete that document's **older** rows* (`ingested_at < this_run`). Concurrent runs converge on the newest; a document is never momentarily empty.
```sql
DELETE FROM rag.chunks WHERE doc_uri = @uri AND ingested_at < TIMESTAMP(@now)
```

<a id="t7"></a>
## T7 · PII survived redaction
```
"...reached at cfo-office@northwind.example."      <- email not redacted
"...call Maria O'Brien on 087 555 0199."          <- local Irish mobile not redacted
```
**Cause:** built-in `EMAIL_ADDRESS` ignores reserved/internal TLDs like `.example`; `PHONE_NUMBER` didn't recognise the local Irish format without a region.
**Fix:** custom regex infoTypes alongside the built-ins (`CORP_EMAIL`, `IE_MOBILE`), then re-ingest.
```
"...reached at [CORP_EMAIL]."   "...call Maria O'Brien on [IE_MOBILE]."
```
Names are intentionally not redacted (see [02](02-ingest-a-document.md)). **Always verify redaction on your own data** — DLP is probabilistic.

<a id="t8"></a>
## T8 · Every answer is `unanswerable`/clearance `public` when using `gcloud run services proxy`
**Cause:** the proxy's token carries no `email` claim → the API correctly falls back to `public` (fail closed).
**Fix:** test with impersonated ID tokens (`--include-email`, see [03](03-query-and-access-control.md)) or put IAP in front ([ADR 0006](../adr/0006-edge-and-authentication-path.md)).

## T9 · `/healthz` returns Google's 404 from the public URL
Cloud Run's front end reserves some paths (including `/healthz`) on `*.run.app`. The **startup probe hits the container internally, so it works**; just don't use `/healthz` as an external check.

## T10 · `terraform apply /tmp/plan` → `Inconsistent dependency lock file`
Run saved plans from the same directory (`terraform/`) they were created in; or simply re-plan.

## T11 · `gcloud run services proxy` / `beta` commands prompt to install a component
Install non-interactively: `gcloud components install beta cloud-run-proxy --quiet`.

## T12 · zsh: `bq get-iam-policy --table $PROJECT:rag.chunks` → `Invalid dataset ID`
`$PROJECT:rag` is parsed as the `:r` (root) modifier. Use `${PROJECT}:rag.chunks`.

## T13 · `gcloud run jobs … --args` with commas in the value
Commas split the list. Use an alternate delimiter: `--args="^@^-c@<code with, commas>"`.

## Diagnostic one-liners
```bash
# last errors from a service, one line each
gcloud logging read 'resource.labels.service_name="rag-ingest" AND severity>=ERROR' --project $PROJECT --limit 5 --format='csv[no-heading](timestamp,textPayload)'
# is anything retrying? (Eventarc backlog)
gcloud pubsub subscriptions list --project $PROJECT --format='table(name.basename(),topic.basename())'
# what does Terraform think exists?
terraform -chdir=terraform state list | wc -l    # 121
```
