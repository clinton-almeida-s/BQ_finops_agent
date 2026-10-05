# BQ FinOps Agent — Architecture Spec

## Overview

An agentic AI system that analyzes BigQuery costs and slot utilization using **only GCP services**, producing actionable optimization recommendations.

## Data Sources (All GCP Native)

| Source | What It Provides | Access Method |
|--------|-----------------|---------------|
| `INFORMATION_SCHEMA.JOBS` | Query metadata, bytes billed, duration, slot_ms | Direct SQL |
| Cloud Monitoring (`bigquery.googleapis.com/slot_allocation`) | Slot utilization over time | Monitoring API |
| BQ Billing Export | Commitment spend, reservation details | BQ tables (auto-populated) |
| BigQuery Metadata API | Dataset/table-level cost attribution | REST API |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GCP Services Layer                       │
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────┐  │
│  │ Cloud Scheduler │ │ Cloud Run    │   │ BigQuery      │  │
│  │ (Nightly)     │──▶│ (Agent)      │──▶│ INFORMATION_  │  │
│  └──────────────┘   └──────┬───────┘   │ SCHEMA.JOBS   │  │
│                            │           └───────┬───────┘  │
│                            │                   │          │
│                            ▼                   ▼          │
│                   ┌──────────────┐   ┌───────────────┐    │
│                   │ Monitoring   │   │ Billing Export│    │
│                   │ API          │   │ (projects/    │    │
│                   │              │   │  billing/     │    │
│                   │              │   │  exports/...) │    │
│                   └──────┬───────┘   └───────────────┘    │
│                          │                                │
│                          ▼                                │
│                   ┌──────────────┐                        │
│                   │ Recommendations│                       │
│                   │ Table (BQ)   │◀───────────────────────┘
│                   └──────┬───────┘                        │
│                          │                                │
│                          ▼                                │
│                   ┌──────────────┐   ┌──────────────────┐ │
│                   │ Looker Studio│   │ Slack/Teams      │ │
│                   │ (Dashboard)  │   │ (Webhook Alert)  │ │
│                   └──────────────┘   └──────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Local Dev
                          ▼
                   ┌──────────────┐
                   │ Claude Code  │
                   │ (CLI Agent)  │
                   └──────────────┘
```

## Core Components

### 1. Data Collector (`collectors/`)

**Purpose:** Gather raw data from BQ and Monitoring into a staging table.

**Queries:**

```sql
-- BQ Jobs (last 30 days)
SELECT
  job_id,
  query,
  sha256_hash(query) as query_fingerprint,
  total_bytes_billed,
  total_slot_ms,
  creation_time,
  user_email,
  dataset_id,
  project_id,
  statement_type,
  cache_hit,
  error_message
FROM `region-us.INFORMATION_SCHEMA.JOBS`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
```

```sql
-- Slot utilization (hourly aggregation)
SELECT
  timestamp,
  reservation_id,
  AVG(slot_capacity) as avg_slots,
  AVG(avg_slot_capacity) as avg_used,
  AVG(avg_slot_capacity) / NULLIF(AVG(slot_capacity), 0) * 100 as utilization_pct
FROM `monitoring.googleapis.com/bigquery.slot_allocation`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY timestamp, reservation_id
```

**Output:** Staging table `finops_staging.raw_data`

### 2. Analysis Engine (`analyzers/`)

Four analyzers, each runs in sequence:

| Analyzer | Input | Output | Savings Estimation |
|----------|-------|--------|-------------------|
| `slot_health` | Slot utilization data | Over/under-provisioned reservations | $/month by right-sizing |
| `query_patterns` | Fingerprinted queries | Duplicate/redundant query groups | Reduction in executions × avg cost |
| `anomaly_detector` | Baseline + current spend | Anomalous spikes | Quantified variance |
| `optimization_scan` | Table metadata | Missing partition/cluster, SELECT * | Estimated % reduction |

### 3. AI Analysis (`agents/`)

Gemini processes the analysis results and produces:
- Natural language explanation of findings
- Prioritized action items
- Risk assessment (what could break if we optimize)

**Prompt pattern:**
```
You are a BigQuery FinOps expert. Given the following analysis results:

[analysis_data]

Provide:
1. Executive summary (2-3 sentences)
2. Top 3 actions with estimated savings
3. Risks and mitigation
4. SQL code for recommended changes
```

### 4. Storage (`models/`)

**Recommendations table schema:**
```sql
CREATE TABLE finops_recommendations.recommendations (
  recommendation_id STRING,
  category STRING,  -- 'slot_optimization', 'query_pattern', 'schema_optimization'
  severity STRING,  -- 'high', 'medium', 'low'
  title STRING,
  description STRING,
  current_state STRING,
  recommended_state STRING,
  estimated_savings_monthly FLOAT64,
  confidence_score FLOAT64,
  sql_code STRING,
  created_at TIMESTAMP,
  status STRING DEFAULT 'new'  -- 'new', 'acknowledged', 'implemented'
);
```

## GCP Service Mapping

| Component | GCP Service | Notes |
|-----------|-------------|-------|
| Scheduler | Cloud Scheduler | Daily at 2 AM UTC |
| Compute | Cloud Run (python:3.11) | Ephemeral, low cost |
| Data Storage | BigQuery | Uses existing tables |
| Dashboard | Looker Studio | Connects to BQ directly |
| Alerts | Cloud Monitoring + Webhook | For critical anomalies |
| Agent Logic | Gemini API (via Google AI SDK) | or Claude if preferred |

## Deployment Steps

1. Create GCP project with BQ + Monitoring APIs enabled
2. Set up service account with:
   - `BigQuery Data Viewer`
   - `BigQuery Job User`
   - `Monitoring Reader`
3. Deploy Cloud Run service with the agent code
4. Configure Cloud Scheduler to trigger daily
5. Connect Looker Studio to the recommendations table
6. (Optional) Set up webhook for Slack/Teams alerts

## Cost to Run

- Cloud Run: ~$0.01-0.05/day (small container, infrequent invocations)
- BQ queries: Minimal (reads from INFORMATION_SCHEMA, no data egress)
- Gemini API: ~$0.001-0.01 per run (small prompts, short responses)

**Total monthly: <$1**

## Project Structure

```
BQ_finops_agent/
├── README.md
├── requirements.txt
├── .env.example
├── main.py                    # Entry point
├── collectors/
│   ├── __init__.py
│   ├── bq_jobs.py            # Query INFORMATION_SCHEMA
│   ├── monitoring.py         # Fetch slot utilization
│   └── billing.py            # Pull billing export
├── analyzers/
│   ├── __init__.py
│   ├── slot_health.py        # Analyze slot usage
│   ├── query_patterns.py     # Group duplicate queries
│   ├── anomaly_detector.py   # Statistical anomaly detection
│   └── optimization_scan.py  # Schema optimization checks
├── agents/
│   ├── __init__.py
│   ├── gemini_agent.py       # LLM analysis
│   └── prompts.py            # Prompt templates
├── models/
│   ├── __init__.py
│   ├── recommendation.py     # Dataclasses
│   └── storage.py            # BQ read/write
└── config.py                  # Environment config
```

## Next Steps

1. ✅ Architecture defined (this doc)
2. ⏳ Implement data collectors
3. ⏳ Build analysis engine
4. ⏳ Add Gemini integration
5. ⏳ Deploy to GCP
6. ⏳ Connect Looker Studio dashboard

---

*Spec created: 2026-10-05*
