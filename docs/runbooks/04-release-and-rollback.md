# 04 · Release & rollback

**When:** shipping a code change, or reverting a bad revision. Rollback is a traffic switch — seconds, no rebuild.

## Release
```bash
make lint test                       # ruff, terraform validate, 18 unit tests
make images TAG=$(git rev-parse --short HEAD)
make deploy TAG=$(git rev-parse --short HEAD)
make eval                            # gate: must print N/N passed
```
```
ID                                    DURATION  IMAGES                                                               STATUS
7ce1b34b-f0fc-4939-ab25-7bdd7f35f7dd  58S       europe-west1-docker.pkg.dev/claude-code-507112/rag/api:v3 (+1 more)  SUCCESS
Service [rag-api] revision [rag-api-00004-h5t] has been deployed and is serving 100 percent of traffic.
Service [rag-ingest] revision [rag-ingest-00004-7gj] has been deployed and is serving 100 percent of traffic.
```
Tags are **immutable** in Artifact Registry (a tag can never be silently repointed) — always use a new tag.

In CI the same flow runs in `.github/workflows/deploy.yml`, gated by the protected `prod` environment.

## Inspect revisions
```bash
gcloud run revisions list --service rag-api --project $PROJECT --region $REGION --limit 5
```
```
NAME               READY  CREATION_TIMESTAMP  IMAGE
rag-api-00004-h5t  True   19:47:01            api@sha256:6589cefe2dc9a01150bd47ab1182249d488b7fbbabf5089070af680112905b7e
rag-api-00003-rv4  True   19:43:38            api@sha256:c25ae470e58b34d9585dad497109b27ae71f0f18724c702b089e0844d4b8b2a8
rag-api-00002-hb6  True   19:39:59            api@sha256:ead0a2c07d862b611fee8ac27320bc6d1583b59bbb9e432242c850d8f5daef15
rag-api-00001-vxr  True   19:33:17            hello@sha256:be0a21e5d7036cc60741cf60ea3b68e169cc2d00f3ad256c94536f32b0a0755c
```

## Rollback (drill executed against the live service)
```bash
gcloud run services update-traffic rag-api --project $PROJECT --region $REGION \
  --to-revisions=rag-api-00003-rv4=100
```
```
URL: https://rag-api-mumqq56yxq-ew.a.run.app
Traffic:
  100% rag-api-00003-rv4
```
Verify, then run `make eval`.

## Roll forward again
```bash
gcloud run services update-traffic rag-api --project $PROJECT --region $REGION --to-latest
```
```
Traffic:
  100% LATEST (currently rag-api-00004-h5t)
```

## Canary (optional)
```bash
gcloud run deploy rag-api ... --no-traffic --tag canary        # new revision, 0% traffic
gcloud run services update-traffic rag-api --to-tags canary=10 # 10% of requests
```
Watch the burn-rate alert for 15 min ([05](05-availability-incident.md)), then `--to-latest`.

## Terraform vs `gcloud run` image drift
Terraform owns the image via `-var api_image=… -var ingest_image=…`. `up.sh` handles this: it carries over whatever is currently deployed and only rolls to a newly built image deliberately. If you hand-roll an image with `gcloud run`, a bare `terraform apply` will show the image as drift (it plans to reset to the placeholder) — always apply through `up.sh` or pass the vars.
