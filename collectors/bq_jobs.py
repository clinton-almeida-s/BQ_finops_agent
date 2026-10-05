"""Collect BQ job data from INFORMATION_SCHEMA."""

import logging
from datetime import datetime
from typing import Optional

from google.cloud import bigquery

logger = logging.getLogger(__name__)


def get_query_jobs(
    project_id: str,
    location: str,
    days_back: int = 30,
    max_results: int = 10000,
) -> list[dict]:
    """Fetch recent BQ jobs with cost data."""
    query = f"""
    SELECT
      job_id,
      query,
      SHA256(hashable_query) as query_fingerprint,
      total_bytes_billed,
      total_slot_ms,
      creation_time,
      user_email,
      dataset_id,
      project_id as query_project,
      statement_type,
      cache_hit,
      error_message,
      total_processed_bytes,
      num_child_jobs
    FROM `{location}.INFORMATION_SCHEMA.JOBS`
    WHERE
      creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
      AND state = 'DONE'
      AND statement_type IN ('SELECT', 'QUERY')
    ORDER BY creation_time DESC
    LIMIT {max_results}
    """

    client = bigquery.Client(project=project_id, location=location)
    job = client.query(query)
    results = job.result()

    jobs = []
    for row in results:
        jobs.append(row.to_dict())

    logger.info("Fetched %d jobs", len(jobs))
    return jobs


def get_query_fingerprints(
    project_id: str,
    location: str,
    days_back: int = 30,
    min_executions: int = 2,
) -> list[dict]:
    """Get query fingerprints grouped by similarity."""
    query = f"""
    SELECT
      SHA256(hashable_query) as fingerprint,
      COUNT(*) as execution_count,
      SUM(total_bytes_billed) as total_bytes_billed,
      SUM(total_slot_ms) as total_slot_ms,
      AVG(total_bytes_billed) as avg_bytes_billed,
      MAX(creation_time) as last_run,
      MIN(creation_time) as first_run,
      ARRAY_AGG(DISTINCT user_email ORDER BY user_email LIMIT 10) as users,
      ANY_VALUE(query) as sample_query,
      ARRAY_AGG(DISTINCT dataset_id LIMIT 10) as datasets
    FROM `{location}.INFORMATION_SCHEMA.JOBS`
    WHERE
      creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
      AND state = 'DONE'
      AND error_message IS NULL
      AND statement_type = 'SELECT'
    GROUP BY fingerprint
    HAVING execution_count >= {min_executions}
    ORDER BY total_bytes_billed DESC
    LIMIT 100
    """

    client = bigquery.Client(project=project_id, location=location)
    job = client.query(query)
    results = job.result()

    return [row.to_dict() for row in results]


def get_top_cost_queries(
    project_id: str,
    location: str,
    days_back: int = 30,
    limit: int = 50,
) -> list[dict]:
    """Get the most expensive queries by bytes billed."""
    query = f"""
    SELECT
      job_id,
      query,
      SHA256(hashable_query) as fingerprint,
      total_bytes_billed,
      total_slot_ms,
      creation_time,
      user_email,
      dataset_id
    FROM `{location}.INFORMATION_SCHEMA.JOBS`
    WHERE
      creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
      AND state = 'DONE'
      AND error_message IS NULL
      AND statement_type = 'SELECT'
    ORDER BY total_bytes_billed DESC
    LIMIT {limit}
    """

    client = bigquery.Client(project=project_id, location=location)
    job = client.query(query)
    results = job.result()

    return [row.to_dict() for row in results]


def get_table_stats(
    project_id: str,
    location: str,
    days_back: int = 30,
) -> list[dict]:
    """Get table-level statistics for optimization scanning."""
    query = f"""
    SELECT
      table_name,
      dataset_id,
      SUM(total_bytes_billed) as total_bytes_billed,
      COUNT(*) as query_count,
      COUNT(DISTINCT user_email) as unique_users,
      MAX(creation_time) as last_accessed
    FROM `{location}.INFORMATION_SCHEMA.JOBS`,
         UNNEST(table_refs) as table_refs
    WHERE
      creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
      AND state = 'DONE'
      AND error_message IS NULL
    GROUP BY dataset_id, table_name
    ORDER BY total_bytes_billed DESC
    LIMIT 100
    """

    client = bigquery.Client(project=project_id, location=location)
    job = client.query(query)
    results = job.result()

    return [row.to_dict() for row in results]
