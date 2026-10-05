"""Collect billing export data."""

import logging
from typing import Optional

from google.cloud import bigquery

logger = logging.getLogger(__name__)


def get_billing_export(
    project_id: str,
    dataset: str = "billing_export",
    months_back: int = 3,
) -> list[dict]:
    """Get BigQuery cost data from billing export."""
    query = f"""
    SELECT
      SUM(cost) as total_cost,
      SUM(cost) FILTER (WHERE service.description LIKE '%BigQuery%') as bq_cost,
      service.description as service,
      labels.`project.id` as project_id,
      EXTRACT(MONTH FROM usage_start_time) as month
    FROM `{project_id}.{dataset}.bigquery_gcp_com_google_cloud_bigquery_project_v1_*`
    WHERE _table_suffix >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL {months_back} MONTH))
    GROUP BY service.description, labels.`project.id`, month
    ORDER BY month DESC, bq_cost DESC
    """

    try:
        client = bigquery.Client(project=project_id)
        job = client.query(query)
        results = job.result()
        return [row.to_dict() for row in results]
    except Exception as e:
        logger.warning("Failed to fetch billing export: %s", e)
        return []


def get_daily_cost(
    project_id: str,
    dataset: str = "billing_export",
    days_back: int = 30,
) -> list[dict]:
    """Get daily BigQuery costs."""
    query = f"""
    SELECT
      DATE(usage_start_time) as date,
      SUM(cost) as daily_cost,
      SUM(usage.amount) as bytes_processed
    FROM `{project_id}.{dataset}.bigquery_gcp_com_google_cloud_bigquery_project_v1_*`
    WHERE _table_suffix >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL {days_back} DAY))
    GROUP BY date
    ORDER BY date DESC
    """

    try:
        client = bigquery.Client(project=project_id)
        job = client.query(query)
        results = job.result()
        return [row.to_dict() for row in results]
    except Exception as e:
        logger.warning("Failed to fetch daily costs: %s", e)
        return []
