# BQ FinOps Agent

Agentic AI system for BigQuery cost optimization — pure GCP, <$1/month to run.

## What It Does

| Capability | What It Finds | Typical Impact |
|------------|---------------|----------------|
| **Slot Health** | Over-provisioned or near-capacity reservations | Right-size slot commits |
| **Query Patterns** | Duplicate/redundant queries with shared fingerprints | Savings via materialized views or scheduled queries |
| **Anomaly Detection** | Cost spikes and upward trends (z-score + linear regression) | Catch budget overruns early |
| **Schema Optimization** | Missing partitions (>10 GB), missing clustering (>1 GB), high string storage | Reduce scan costs 60-90% |

Results are stored in BigQuery and visualized via Looker Studio (setup in this doc).

---

## Quick Start — No Credentials Needed

```bash
cd C:\Users\clint\brainstorming_ideas\BQ_finops_agent
pip install -r requirements.txt

# Demo with sample data (no GCP project, no API keys)
python main.py --mode analyze --sample

# Generate a browser-ready HTML report from sample data
python main.py --mode report --sample --output bq_finops_report_demo.html
```

The sample mode exercises every analyzer against realistic synthetic data so you can show the full pipeline output before provisioning anything.

---

## Real Mode — With GCP Access

```bash
# Copy and fill in credentials
cp .env.example .env
# Edit .env (see Setup Guide below)

# Run against your real project
python main.py --mode analyze

# Report from stored recommendations
python main.py --mode report

# HTML report (real data)
python main.py --mode report --limit 50
```

---

## Project Structure

```
BQ_finops_agent/
├── main.py                    # CLI entry point (--mode analyze|report, --sample, --output)
├── pipeline.py                # FinOpsAgent orchestrator
├── config.py                  # Env-var config with validation
├── report_html.py             # HTML report generator (works in sample & real mode)
├── requirements.txt
├── .env.example
├── samples/
│   ├── __init__.py
│   ├── data.py                # Synthetic datasets (fingerprints, slots, costs, table stats)
│   └── fake_clients.py        # Monkey-patches google.cloud for zero-key testing
├── collectors/
│   ├── bq_jobs.py             # INFORMATION_SCHEMA.JOBS queries
│   ├── monitoring.py          # Cloud Monitoring slot_allocation series
│   └── billing.py             # Billing export table access
├── analyzers/
│   ├── slot_health.py         # Under/over-provisioned reservation detection
│   ├── query_patterns.py      # SHA256 fingerprint grouping + savings estimate
│   ├── anomaly_detector.py    # Z-score spike + linear-trend detection
│   └── optimization_scan.py   # Missing partition/cluster/string checks
├── agents/
│   └── gemini_agent.py        # Gemini 2.5 Flash analysis & plain-English summaries
└── models/
    ├── recommendation.py      # Recommendation dataclass
    └── storage.py             # BigQuery read/write wrapper
```

---

## Setup Guide — Production Deployment

### 1. Service Account Setup (Workload Identity)

**No SA key file needed.** Cloud Run authenticates directly using its own service account with least-privilege roles.

```bash
export PROJECT_ID="your-project-id"

# Create Cloud Run service account with minimal roles
gcloud iam service-accounts create bq-finops-agent \
  --display-name "BQ FinOps Agent" \
  --project $PROJECT_ID

# Grant least-privilege roles directly to the Cloud Run SA
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:bq-finops-agent@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.user"          # Query INFORMATION_SCHEMA.JOBS
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:bq-finops-agent@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"     # Read billing export tables
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:bq-finops-agent@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/monitoring.viewer"       # Read slot utilization time series
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:bq-finops-agent@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/billing.costsUser"       # Read billing export
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:bq-finops-agent@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"     # Write recommendations table
```

---

### 2. Manage Secrets — Secret Manager

Only the **Gemini API key** needs to be stored in Secret Manager (SA key is no longer needed).

```bash
# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com

# --- Store Gemini API key ---
gcloud secrets create finops-gemini-key \
  --project=$PROJECT_ID \
  --replication-policy="automatic"

echo "AIzaSy..." | gcloud secrets versions add finops-gemini-key \
  --project=$PROJECT_ID \
  --data-file=-
```

Grant the Cloud Run service account permission to read the secret:

```bash
RUNNER_SA="bq-finops-agent@$PROJECT_ID.iam.gserviceaccount.com"

gcloud secrets add-iam-policy-binding finops-gemini-key \
  --project=$PROJECT_ID \
  --member="serviceAccount:$RUNNER_SA" \
  --role="roles/secretmanager.secretAccessor"
```

---

### 3. Create the Recommendations Dataset

```bash
bq --project_id=$PROJECT_ID mk --dataset finops_recommendations
```

---

### 4. Deploy to Cloud Run (Workload Identity — no key file)

This is the recommended production setup. Cloud Run authenticates directly; only the Gemini key needs Secret Manager.

```bash
# Enable required APIs
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  bigquery.googleapis.com \
  monitoring.googleapis.com \
  secretmanager.googleapis.com \
  generativelanguage.googleapis.com

# Deploy (builds from Dockerfile, runs as the Cloud Run service account)
gcloud run deploy bq-finops-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account bq-finops-agent@$PROJECT_ID.iam.gserviceaccount.com \
  --set-secrets \
    GEMINI_API_KEY=finops-gemini-key:latest \
  --set-env-vars \
    GOOGLE_CLOUD_PROJECT=$PROJECT_ID,\
    WORKLOAD_IDENTITY=true,\
    ANALYSIS_DAYS_BACK=30,\
    SLOT_ANALYSIS_HOURS_BACK=168,\
    ANOMALY_THRESHOLD_STDDEV=2.0
```

The `WORKLOAD_IDENTITY=true` flag tells the agent to skip SA key authentication and use Cloud Run's built-in identity instead.

---

### 5. Schedule Nightly Runs

```bash
# Create an HTTP-triggered scheduler job
gcloud scheduler jobs create http bq-finops-daily \
  --project=$PROJECT_ID \
  --location=us-central1 \
  --schedule="0 2 * * *" \
  --uri="https://bq-finops-agent-XXXX.a.run.app/" \
  --http-method=POST \
  --oauth-service-account-email="bq-finops-agent@$PROJECT_ID.iam.gserviceaccount.com"
```

---

### 6. Connect Looker Studio Dashboard

1. Open [Looker Studio](https://lookerstudio.google.com)
2. Create a new report → Google BigQuery connector
3. Select your project → dataset `finops_recommendations` → table `recommendations`
4. Add KPI tiles (total savings, recommendations by severity) and a table visualization
5. Set refresh to daily (matches the scheduler)

---

## Cost Estimate (Production)

| Component | Monthly Cost |
|-----------|-------------|
| Cloud Run (1 invocation/day, 256 MB) | ~$0.30 |
| BigQuery INFORMATION_SCHEMA queries | <$0.01 |
| Billing export reads | Free (already paid) |
| Monitoring API calls | <$0.01 |
| Gemini API (~30 calls/month) | ~$0.05 |
| Secret Manager | Free tier covers this |
| **Total** | **<$1/month** |

---

## Commands Reference

```bash
# Local dev
python main.py --mode analyze --sample              # Demo (no credentials)
python main.py --mode report --sample               # HTML report (no credentials)
python main.py --mode analyze                        # Real analysis
python main.py --mode report                         # Report from stored BQ data
python main.py --mode report --output my_report.html # Save HTML report

# Makefile shortcuts
make install    # pip install -r requirements.txt
make run        # python main.py --mode analyze
make report     # python main.py --mode report
make deploy     # gcloud run deploy (sets PROJECT_ID env var)
make schedule   # creates Cloud Scheduler job
```

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design, data flow diagrams, and SQL queries.

---
