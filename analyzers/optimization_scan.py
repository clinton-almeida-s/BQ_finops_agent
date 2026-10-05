"""Scan for schema optimization opportunities."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def scan_schema_optimizations(
    table_stats: list[dict],
) -> list[dict]:
    """Check tables for missing partitions, clustering, etc."""
    recommendations = []

    for row in table_stats:
        table_name = row.get("table_name", "")
        dataset = row.get("dataset_id", "")
        total_bytes = row.get("total_bytes", 0)
        partition_expr = row.get("partition_expression", "")
        clustering_fields = row.get("clustering_fields", "") or ""

        # Check if table is large but not partitioned
        if total_bytes > 10_000_000_000 and not partition_expr:  # >10GB, no partition
            recommendations.append({
                "category": "schema_optimization",
                "severity": "high",
                "title": f"Large table '{dataset}.{table_name}' not partitioned",
                "description": f"Table is {total_bytes/(1024**3):.1f} GB but has no partitioning. Partitioning by ingestion date or event timestamp could reduce scan costs by 60-90% for time-filtered queries.",
                "current_state": f"{total_bytes/(1024**3):.1f} GB, no partition",
                "recommended_state": "Add DATE or TIMESTAMP partition on ingestion_time or event_date",
                "estimated_savings_monthly": total_bytes / (1024**3) * 6.25 * 0.7 / 30,  # Monthly estimate
                "confidence_score": 0.75,
                "sql_code": f"-- Add partitioning (requires table rewrite)\n-- CREATE TABLE `{dataset}.{table_name}_partitioned`\n-- PARTITION BY DATE(event_timestamp)\n-- AS SELECT * FROM `{dataset}.{table_name}`",
                "metadata": {
                    "table_name": table_name,
                    "dataset": dataset,
                    "total_bytes": total_bytes,
                },
            })

        # Check if table is large but not clustered
        if total_bytes > 1_000_000_000 and not clustering_fields:  # >1GB, no clustering
            recommendations.append({
                "category": "schema_optimization",
                "severity": "medium",
                "title": f"Large table '{dataset}.{table_name}' not clustered",
                "description": f"Table is {total_bytes/(1024**3):.1f} GB with no clustering. Consider clustering by frequently filtered columns.",
                "current_state": f"{total_bytes/(1024**3):.1f} GB, no clustering",
                "recommended_state": "Add CLUSTER BY columns frequently used in WHERE clauses",
                "estimated_savings_monthly": total_bytes / (1024**3) * 6.25 * 0.3 / 30,
                "confidence_score": 0.6,
                "metadata": {
                    "table_name": table_name,
                    "dataset": dataset,
                    "total_bytes": total_bytes,
                },
            })

        # Check for unbounded strings (wastes space)
        long_string_bytes = row.get("num_long_string_bytes", 0) or 0
        if long_string_bytes > total_bytes * 0.5 and total_bytes > 1_000_000_000:
            recommendations.append({
                "category": "schema_optimization",
                "severity": "low",
                "title": f"Table '{dataset}.{table_name}' has high string storage",
                "description": f"{long_string_bytes/(1024**3):.1f} GB of {total_bytes/(1024**3):.1f} GB is long string data. Consider STRING->JSON or compression.",
                "current_state": f"{long_string_bytes/(1024**3):.1f} GB strings",
                "recommended_state": "Use JSON or repeated fields for flexible schemas",
                "estimated_savings_monthly": long_string_bytes / (1024**3) * 6.25 * 0.2 / 30,
                "confidence_score": 0.5,
                "metadata": {
                    "table_name": table_name,
                    "long_string_bytes": long_string_bytes,
                },
            })

    return sorted(recommendations, key=lambda x: x["estimated_savings_monthly"], reverse=True)
