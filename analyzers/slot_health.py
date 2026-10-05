"""Analyze slot utilization health."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def analyze_slot_health(
    slot_data: list[dict],
    reservations: list[dict],
) -> list[dict]:
    """Analyze slot reservation health and identify issues."""
    recommendations = []

    for reservation in reservations:
        reservation_id = reservation.get("reservation_id", "unknown")
        config = reservation.get("config", {})
        slot_capacity = config.get("slot_capacity", 0)

        # Find utilization data
        utilization = None
        for sd in slot_data:
            if sd.get("reservation_id") == reservation_id:
                utilization = sd
                break

        if not utilization:
            continue

        metrics = utilization.get("metrics", {})
        avg_util = metrics.get("average_utilization", 0)
        min_util = metrics.get("minimum_utilization", 0)
        max_util = metrics.get("maximum_utilization", 0)

        # Down-sized detection
        if avg_util < 0.3:
            recommendations.append({
                "category": "slot_optimization",
                "severity": "high",
                "title": f"Reservation '{reservation_id}' is over-provisioned",
                "description": f"Average utilization is only {avg_util*100:.1f}%. Consider downsizing from {slot_capacity} to ~{int(slot_capacity * 0.5)} slots.",
                "current_state": f"Capacity: {slot_capacity} slots, Avg utilization: {avg_util*100:.1f}%",
                "recommended_state": f"Reduce to {int(slot_capacity * 0.5)} slots",
                "estimated_savings_monthly": slot_capacity * 0.5 * 10,  # Rough estimate
                "confidence_score": 0.85,
                "metadata": {"reservation_id": reservation_id, "avg_utilization": avg_util},
            })

        # Under-utilized detection
        elif avg_util > 0.85:
            recommendations.append({
                "category": "slot_optimization",
                "severity": "medium",
                "title": f"Reservation '{reservation_id}' is near capacity",
                "description": f"Average utilization is {avg_util*100:.1f}%. Risk of throttling during peak usage.",
                "current_state": f"Capacity: {slot_capacity} slots, Avg utilization: {avg_util*100:.1f}%",
                "recommended_state": f"Increase to {int(slot_capacity * 1.2)} slots",
                "estimated_savings_monthly": 0,
                "confidence_score": 0.7,
                "metadata": {"reservation_id": reservation_id, "avg_utilization": avg_util},
            })

        # Idle detection
        if max_util < 0.1:
            recommendations.append({
                "category": "slot_optimization",
                "severity": "high",
                "title": f"Reservation '{reservation_id}' appears idle",
                "description": f"Maximum utilization was only {max_util*100:.1f}%. Consider deleting or consolidating.",
                "current_state": f"Capacity: {slot_capacity} slots, Max utilization: {max_util*100:.1f}%",
                "recommended_state": "Delete or merge with another reservation",
                "estimated_savings_monthly": slot_capacity * 15,
                "confidence_score": 0.9,
                "metadata": {"reservation_id": reservation_id, "max_utilization": max_util},
            })

    return recommendations
