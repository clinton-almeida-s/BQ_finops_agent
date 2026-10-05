"""Storage layer for BigQuery."""

import logging
from datetime import datetime
from typing import Optional

from google.cloud import bigquery

from .recommendation import Recommendation, Status

logger = logging.getLogger(__name__)


class BQStorage:
    """BigQuery storage for recommendations and analysis data."""

    def __init__(self, project_id: str, location: str = "us"):
        self.client = bigquery.Client(project=project_id, location=location)
        self.project_id = project_id
        self.location = location

    def _get_dataset_id(self, dataset: str) -> str:
        """Get fully qualified dataset ID."""
        return f"{self.project_id}.{dataset}"

    def ensure_datasets(self) -> None:
        """Create datasets if they don't exist."""
        datasets = ["finops_staging", "finops_recommendations"]
        for ds in datasets:
            dataset_id = self._get_dataset_id(ds)
            try:
                self.client.get_dataset(dataset_id)
            except Exception:
                logger.info("Creating dataset: %s", dataset_id)
                self.client.create_dataset(dataset_id)

    def save_recommendation(self, rec: Recommendation) -> bool:
        """Save a single recommendation."""
        table = f"{self.project_id}.{self.project_id}.recommendations"
        rows = [rec.to_dict()]

        try:
            errors = self.client.insert_rows_json(table, rows)
            if errors:
                logger.error("Insert errors: %s", errors)
                return False
            return True
        except Exception as e:
            logger.error("Failed to save recommendation: %s", e)
            return False

    def save_recommendations(self, recommendations: list[Recommendation]) -> int:
        """Save multiple recommendations. Returns count saved."""
        if not recommendations:
            return 0

        table = f"{self.project_id}.{self.project_id}.recommendations"
        rows = [rec.to_dict() for rec in recommendations]

        try:
            errors = self.client.insert_rows_json(table, rows)
            if errors:
                logger.error("Insert errors: %s", errors)
                return 0
            logger.info("Saved %d recommendations", len(recommendations))
            return len(recommendations)
        except Exception as e:
            logger.error("Failed to save recommendations: %s", e)
            return 0

    def get_recommendations(
        self,
        status: Optional[Status] = None,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> list[Recommendation]:
        """Retrieve recommendations with optional filters."""
        dataset = self._get_dataset_id("finops_recommendations")
        table = f"{dataset}.recommendations"

        query = f"SELECT * FROM `{table}`"
        conditions = []
        params = {}

        if status:
            conditions.append("status = @status")
            params["status"] = status.value
        if category:
            conditions.append("category = @category")
            params["category"] = category

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += f" ORDER BY created_at DESC LIMIT {limit}"

        client = bigquery.Client(project=self.project_id, location=self.location)
        job = client.query(query, params=params)
        results = job.result()

        recommendations = []
        for row in results:
            rec = Recommendation.from_dict(row.to_dict())
            recommendations.append(rec)

        return recommendations

    def get_query_fingerprints(self, days_back: int = 30) -> list[dict]:
        """Get query fingerprints grouped by similarity."""
        query = f"""
        SELECT
          SHA256(hashable_query) as fingerprint,
          COUNT(*) as execution_count,
          SUM(total_bytes_billed) as total_bytes,
          SUM(total_slot_ms) as total_slot_ms,
          MAX(created_time) as last_run,
          ARRAY_AGG(DISTINCT user_email ORDER BY user_email LIMIT 5) as users,
          ANY_VALUE(query) as sample_query
        FROM `{self.project_id}.{self.location}.INFORMATION_SCHEMA.JOBS`
        WHERE
          creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days_back} DAY)
          AND statement_type = 'SELECT'
          AND state = 'DONE'
          AND error_message IS NULL
        GROUP BY fingerprint
        HAVING execution_count > 1
        ORDER BY total_bytes DESC
        LIMIT 100
        """

        client = bigquery.Client(project=self.project_id, location=self.location)
        job = client.query(query)
        results = job.result()

        return [row.to_dict() for row in results]

    def get_slot_utilization(self, hours_back: int = 168) -> list[dict]:
        """Get slot utilization data from Monitoring."""
        # This will use the Monitoring API directly
        # For now, return placeholder - actual implementation in collectors/
        return []
