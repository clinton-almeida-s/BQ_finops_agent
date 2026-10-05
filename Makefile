PROJECT_ID ?= $(shell gcloud config get-value project 2>/dev/null)
GEMINI_API_KEY ?=
CREDENTIALS ?=

.PHONY: install dev test run report sample report-html deploy schedule help

install:
	pip install -r requirements.txt

dev:
	python -m pip install -e .

test:
	pytest tests/ -v

run:
	python main.py --mode analyze

sample:
	python main.py --mode analyze --sample

report-html:
	python main.py --mode report --sample --output bq_finops_report.html

deploy:
ifndef PROJECT_ID
	$(error PROJECT_ID is required: make deploy PROJECT_ID=my-project)
endif
	gcloud run deploy bq-finops-agent \
		--source . \
		--region us-central1 \
		--allow-unauthenticated \
		--service-account bq-finops-agent@$(PROJECT_ID).iam.gserviceaccount.com \
		--set-secrets \
			GOOGLE_APPLICATION_CREDENTIALS=finops-sa-key:latest,\
			GEMINI_API_KEY=finops-gemini-key:latest \
		--set-env-vars \
			GOOGLE_CLOUD_PROJECT=$(PROJECT_ID),\
			GCP_SECRET_MODE=true,\
			ANALYSIS_DAYS_BACK=30,\
			SLOT_ANALYSIS_HOURS_BACK=168,\
			ANOMALY_THRESHOLD_STDDEV=2.0

schedule:
ifndef PROJECT_ID
	$(error PROJECT_ID is required: make schedule PROJECT_ID=my-project)
endif
	gcloud scheduler jobs create http bq-finops-daily \
		--project=$(PROJECT_ID) \
		--location=us-central1 \
		--schedule="0 2 * * *" \
		--uri="https://bq-finops-agent-$(shell gcloud run services describe bq-finops-agent --region us-central1 --format='value(status.url)' 2>/dev/null | sed 's|https://||')" \
		--http-method=POST \
		--oauth-service-account-email="bq-finops-agent@$(PROJECT_ID).iam.gserviceaccount.com"

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
