"""Collect slot utilization from Cloud Monitoring."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from google.cloud import monitoring_v3

logger = logging.getLogger(__name__)


def get_slot_allocation(
    project_id: str,
    hours_back: int = 168,
) -> list[dict]:
    """Fetch slot allocation data from Monitoring API."""
    client = monitoring_v3.MetricServiceClient()

    project_name = client.project_path(project_id)
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours_back)

    # BigQuery slot allocation metric
    metric_filter = (
        'metric.type="bigquery.googleapis.com/slot_allocation/slot_utilization"'
        f'AND resource.type="bigquery_reservation"'
    )

    points = []
    try:
        response = client.list_time_series(
            request={
                "name": project_name,
                "filter": metric_filter,
                "interval": {
                    "start_time": {"seconds": int(start_time.timestamp())},
                    "end_time": {"seconds": int(end_time.timestamp())},
                },
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )

        for ts in response:
            points.append({
                "resource": ts.resource.labels if ts.resource else {},
                "metric": ts.metric.labels if ts.metric else {},
                "points": [
                    {
                        "start_time": str(p.start_time),
                        "end_time": str(p.end_time),
                        "value": p.value.float_value if p.value.float_value else 0,
                    }
                    for p in ts.points
                ] if ts.points else [],
            })

        logger.info("Fetched %d time series", len(points))
    except Exception as e:
        logger.warning("Failed to fetch slot data: %s", e)

    return points


def get_reservation_utilization(
    project_id: str,
    hours_back: int = 168,
) -> dict:
    """Analyze reservation utilization and return summary."""
    points = get_slot_allocation(project_id, hours_back)

    reservations = {}
    for ts in points:
        labels = {**ts.get("resource", {}), **ts.get("metric", {})}
        reservation_id = labels.get("reservation_id", "unknown")
        values = [p["value"] for p in ts.get("points", []) if p.get("value")]

        if values:
            reservations[reservation_id] = {
                "avg_utilization": sum(values) / len(values),
                "min_utilization": min(values),
                "max_utilization": max(values),
                "data_points": len(values),
            }

    return {
        "project_id": project_id,
        "hours_analyzed": hours_back,
        "reservations": reservations,
    }
