"""Analyze query patterns for duplication and waste."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def analyze_query_patterns(
    fingerprints: list[dict],
) -> list[dict]:
    """Find duplicate or redundant query patterns."""
    recommendations = []

    for fp in fingerprints:
        exec_count = fp.get("execution_count", 0)
        total_bytes = fp.get("total_bytes_billed", 0)
        avg_bytes = fp.get("avg_bytes_billed", 0)
        sample_query = fp.get("sample_query", "")

        # Skip very low-impact queries
        if total_bytes < 1_000_000_000:  # Less than 1GB total
            continue

        # Calculate potential savings
        # If we cache or materialize, could save ~80% on repeated executions
        estimated_savings_bytes = total_bytes * 0.8
        estimated_savings_gb = estimated_savings_bytes / (1024 ** 3)
        # $6.25 per TB scanned
        estimated_savings_monthly = estimated_savings_gb * 6.25 / 1000

        if exec_count > 10 and total_bytes > 10_000_000_000:  # >10GB, >10 runs
            recommendations.append({
                "category": "query_pattern",
                "severity": "high" if exec_count > 50 else "medium",
                "title": f"High-frequency query executed {exec_count} times",
                "description": f"This query has run {exec_count} times, scanning {total_bytes/(1024**3):.1f} GB total. Consider a materialized view or scheduled query.",
                "current_state": f"Executions: {exec_count}, Total bytes: {total_bytes/(1024**3):.1f} GB",
                "recommended_state": "Create materialized view or scheduled query",
                "estimated_savings_monthly": estimated_savings_monthly,
                "confidence_score": 0.8,
                "sql_code": f"-- Create materialized view\nCREATE MATERIALIZED VIEW `{fp.get('datasets', [''])[0]}.mv_{hash(sample_query) % 10000}` AS\n{sample_query}",
                "metadata": {
                    "fingerprint": fp.get("fingerprint"),
                    "execution_count": exec_count,
                    "total_bytes": total_bytes,
                },
            })

        # SELECT * anti-pattern
        if "*]" in sample_query.upper() and total_bytes > 5_000_000_000:
            recommendations.append({
                "category": "query_pattern",
                "severity": "medium",
                "title": "Query uses SELECT * on large table",
                "description": f"This query uses SELECT * and scans {total_bytes/(1024**3):.1f} GB. Specify columns to reduce scanned data.",
                "current_state": f"SELECT * query, {total_bytes/(1024**3):.1f} GB scanned",
                "recommended_state": "Replace SELECT * with specific columns",
                "estimated_savings_monthly": estimated_savings_monthly * 0.5,
                "confidence_score": 0.6,
                "metadata": {
                    "fingerprint": fp.get("fingerprint"),
                    "total_bytes": total_bytes,
                },
            })

    return sorted(recommendations, key=lambda x: x["estimated_savings_monthly"], reverse=True)
