PROJECT ?= $(shell gcloud config get-value project 2>/dev/null)
REGION  ?= europe-west1
TAG     ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
TF       = terraform -chdir=terraform
REPO     = $(REGION)-docker.pkg.dev/$(PROJECT)/rag
BUILD_SA = projects/$(PROJECT)/serviceAccounts/rag-build@$(PROJECT).iam.gserviceaccount.com

.PHONY: help install lint test bootstrap init plan apply images deploy seed eval proxy destroy
help: ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install: ## create venv + dev deps
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt
lint: ## ruff + terraform fmt/validate
	.venv/bin/ruff check src tests eval && .venv/bin/ruff format --check src tests eval
	$(TF) fmt -check -recursive && $(TF) validate
test: ## unit tests
	.venv/bin/pytest -q

bootstrap: ## one-time: create the Terraform state bucket
	./scripts/bootstrap.sh $(PROJECT) $(REGION)
init:
	$(TF) init -backend-config="bucket=$(PROJECT)-tfstate"
plan: init ## terraform plan (expects terraform/terraform.tfvars)
	$(TF) plan
apply: init ## terraform apply
	$(TF) apply

images: ## build + push both images with Cloud Build (dedicated build SA, SLSA provenance)
	gcloud builds submit --project $(PROJECT) --region $(REGION) --config cloudbuild.yaml \
	  --service-account $(BUILD_SA) --gcs-source-staging-dir gs://$(PROJECT)-build-staging/src \
	  --substitutions _REPO=$(REPO),_TAG=$(TAG) .
deploy: ## roll the built images onto Cloud Run
	gcloud run services update rag-api    --project $(PROJECT) --region $(REGION) --image $(REPO)/api:$(TAG)
	gcloud run services update rag-ingest --project $(PROJECT) --region $(REGION) --image $(REPO)/ingest:$(TAG)

seed: ## upload the sample corpus -> triggers ingestion via Eventarc
	gcloud storage rsync -r sample-docs gs://$(PROJECT)-rag-docs
eval: ## run the golden-set evaluation against the deployed API
	.venv/bin/python eval/run_eval.py --project $(PROJECT) \
	  --url $$(gcloud run services describe rag-api --project $(PROJECT) --region $(REGION) --format 'value(status.url)') \
	  --out docs/eval-results.md
proxy: ## authenticated local proxy to the private API -> http://localhost:8080
	gcloud run services proxy rag-api --project $(PROJECT) --region $(REGION) --port 8080

destroy: init ## tear everything down (stops all spend)
	$(TF) destroy
