"""Sample data for testing without real GCP credentials."""

from datetime import datetime, timedelta
import random

# Simulated query fingerprints (duplicate/redundant queries)
SAMPLE_FINGERPRINTS = [
    {
        "fingerprint": "a1b2c3d4",
        "execution_count": 157,
        "total_bytes_billed": 850_000_000_000,  # 850 GB
        "avg_bytes_billed": 5_414_000_000,
        "last_run": "2026-10-04T23:15:00Z",
        "first_run": "2026-07-01T08:00:00Z",
        "users": ["analyst1@company.com", "analyst2@company.com"],
        "sample_query": "SELECT * FROM `project.analytics.events` WHERE date >= '2026-01-01'",
        "datasets": ["analytics"],
    },
    {
        "fingerprint": "e5f6g7h8",
        "execution_count": 73,
        "total_bytes_billed": 420_000_000_000,
        "avg_bytes_billed": 5_753_424_657,
        "last_run": "2026-10-04T22:30:00Z",
        "first_run": "2026-08-15T10:00:00Z",
        "users": ["reporting@company.com"],
        "sample_query": "SELECT user_id, event_type FROM `project.analytics.events` GROUP BY 1,2",
        "datasets": ["analytics"],
    },
    {
        "fingerprint": "i9j0k1l2",
        "execution_count": 312,
        "total_bytes_billed": 1_200_000_000_000,
        "avg_bytes_billed": 3_846_153_846,
        "last_run": "2026-10-05T01:00:00Z",
        "first_run": "2026-01-01T00:00:00Z",
        "users": ["dashboards@company.com", "mstr-service@company.com"],
        "sample_query": "SELECT date, revenue, users FROM `project.finance.daily_metrics` WHERE date > '2026-01-01'",
        "datasets": ["finance"],
    },
    {
        "fingerprint": "m3n4o5p6",
        "execution_count": 28,
        "total_bytes_billed": 15_000_000_000,
        "avg_bytes_billed": 535_714_285,
        "last_run": "2026-10-03T14:22:00Z",
        "first_run": "2026-09-01T09:00:00Z",
        "users": ["data-eng@company.com"],
        "sample_query": "SELECT * FROM `project.raw.customer_events` LIMIT 1000",
        "datasets": ["raw"],
    },
]

# Simulated slot utilization
SAMPLE_SLOTS = {
    "project_id": "demo-project",
    "hours_analyzed": 168,
    "reservations": {
        "projects/demo-project/locations/us/reservations/all-reservation": {
            "avg_utilization": 0.12,
            "min_utilization": 0.02,
            "max_utilization": 0.45,
            "data_points": 168,
            "slot_capacity": 1000,
        },
        "projects/demo-project/locations/us/reservations/dedicated-highpriority": {
            "avg_utilization": 0.91,
            "min_utilization": 0.78,
            "max_utilization": 1.0,
            "data_points": 168,
            "slot_capacity": 500,
        },
    },
}

# Simulated daily billing costs (last 30 days)
SAMPLE_DAILY_COSTS = []
base_cost = 250.00
random.seed(42)
for i in range(30):
    date = (datetime.utcnow() - timedelta(days=29 - i)).strftime("%Y-%m-%d")
    # Normal day with some noise + one spike on day 18
    cost = base_cost + random.gauss(0, 30)
    if i == 17:
        cost = 850.00  # Anomaly spike
    SAMPLE_DAILY_COSTS.append({"date": date, "daily_cost": round(cost, 2), "bytes_processed": int(cost * 40_000_000)})

# Simulated table stats
SAMPLE_TABLE_STATS = [
    {
        "table_name": "user_events_raw",
        "dataset_id": "analytics",
        "total_bytes": 45_000_000_000_000,  # 45 GB
        "partition_expression": "",
        "clustering_fields": "",
        "num_long_string_bytes": 12_000_000_000,
    },
    {
        "table_name": "daily_metrics",
        "dataset_id": "finance",
        "total_bytes": 120_000_000_000_000,  # 120 GB
        "partition_expression": "DATE(event_timestamp)",
        "clustering_fields": "metric_name,region",
        "num_long_string_bytes": 5_000_000_000,
    },
    {
        "table_name": "customer_profiles",
        "dataset_id": "crm",
        "total_bytes": 25_000_000_000_000,  # 25 GB
        "partition_expression": "",
        "clustering_fields": "",
        "num_long_string_bytes": 18_000_000_000,
    },
    {
        "table_name": "ad_impressions",
        "dataset_id": "marketing",
        "total_bytes": 8_000_000_000_000,  # 8 GB
        "partition_expression": "",
        "clustering_fields": "campaign_id",
        "num_long_string_bytes": 2_000_000_000,
    },
]


def generate_sample_recommendations() -> list[dict]:
    """Generate realistic recommendations from sample data."""
    from analyzers.query_patterns import analyze_query_patterns
    from analyzers.anomaly_detector import detect_cost_anomalies, detect_trend_anomaly
    from analyzers.slot_health import analyze_slot_health
    from analyzers.optimization_scan import scan_schema_optimizations

    recs = []
    recs.extend(analyze_query_patterns(SAMPLE_FINGERPRINTS))
    recs.extend(analyze_slot_health(SAMPLE_SLOTS.get("reservations", []), []))
    recs.extend(detect_cost_anomalies(SAMPLE_DAILY_COSTS))
    trend = detect_trend_anomaly(SAMPLE_DAILY_COSTS)
    if trend:
        recs.append(trend)
    recs.extend(scan_schema_optimizations(SAMPLE_TABLE_STATS))
    return recs
