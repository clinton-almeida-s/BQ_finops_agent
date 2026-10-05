"""Statistical anomaly detection for BQ costs (pure stdlib, no numpy/scipy)."""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _stddev(values: list[float], mean_val: float) -> float:
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def detect_cost_anomalies(
    daily_costs: list[dict],
    stddev_threshold: float = 2.0,
) -> list[dict]:
    """Detect anomalous cost spikes using z-score."""
    if len(daily_costs) < 7:
        logger.warning("Insufficient data for anomaly detection (need 7+ days)")
        return []

    costs = [d.get("daily_cost", 0) or 0 for d in daily_costs]
    dates = [d.get("date") for d in daily_costs]

    if not costs or len(costs) < 7:
        return []

    mean_cost = _mean(costs)
    std_cost = _stddev(costs, mean_cost)

    if std_cost == 0:
        return []

    recommendations = []

    for date, cost in zip(dates, costs):
        z_score = (cost - mean_cost) / std_cost

        if z_score > stddev_threshold:
            percent_above = ((cost - mean_cost) / mean_cost) * 100
            recommendations.append({
                "category": "anomaly",
                "severity": "high" if z_score > 3 else "medium",
                "title": f"Cost spike detected on {date}",
                "description": f"Daily cost ${cost:,.2f} is {z_score:.1f} standard deviations above mean (${mean_cost:,.2f}). Increase of {percent_above:.1f}%.",
                "current_state": f"Daily cost: ${cost:,.2f} (baseline: ${mean_cost:,.2f})",
                "recommended_state": "Investigate top queries for this date",
                "estimated_savings_monthly": 0,
                "confidence_score": min(0.95, 0.7 + (z_score - stddev_threshold) * 0.1),
                "metadata": {
                    "date": date,
                    "cost": cost,
                    "mean": mean_cost,
                    "std": std_cost,
                    "z_score": z_score,
                },
            })

    # Check for unexpected drops
    for date, cost in zip(dates, costs):
        z_score = (cost - mean_cost) / std_cost
        if z_score < -stddev_threshold:
            percent_below = ((mean_cost - cost) / mean_cost) * 100
            recommendations.append({
                "category": "anomaly",
                "severity": "low",
                "title": f"Unexpected cost drop on {date}",
                "description": f"Daily cost ${cost:,.2f} is {abs(z_score):.1f} standard deviations below mean. Could indicate missed queries or dashboard failures.",
                "current_state": f"Daily cost: ${cost:,.2f} (baseline: ${mean_cost:,.2f})",
                "recommended_state": "Verify all expected queries ran",
                "estimated_savings_monthly": 0,
                "confidence_score": 0.6,
                "metadata": {
                    "date": date,
                    "cost": cost,
                    "mean": mean_cost,
                    "std": std_cost,
                    "z_score": z_score,
                },
            })

    return sorted(recommendations, key=lambda x: abs(x["metadata"]["z_score"]), reverse=True)


def _linear_regression(
    x_values: list[int], y_values: list[float]
) -> tuple[float, float, float, float]:
    """Return (slope, intercept, r_squared, p_value_proxy)."""
    n = len(x_values)
    sum_x = sum(x_values)
    sum_y = sum(y_values)
    sum_xy = sum(x * y for x, y in zip(x_values, y_values))
    sum_x2 = sum(x * x for x in x_values)
    sum_y2 = sum(y * y for y in y_values)

    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0, 0.0, 0.0, 1.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    y_mean = sum_y / n
    ss_tot = sum((y - y_mean) ** 2 for y in y_values)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))

    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    # Approximate p-value proxy (not exact but sufficient for trend detection)
    if n > 2 and ss_tot > 0:
        t_stat = slope * math.sqrt(sum((x - sum_x / n) ** 2 for x in x_values)) / math.sqrt(ss_res / (n - 2)) if ss_res > 0 else float('inf')
        # Rough approximation: p < 0.05 when |t| > ~2 for moderate n
        p_proxy = 1.0 / (1.0 + abs(t_stat))
    else:
        p_proxy = 1.0

    return slope, intercept, r_squared, p_proxy


def detect_trend_anomaly(
    daily_costs: list[dict],
) -> Optional[dict]:
    """Detect if costs are trending upward consistently."""
    if len(daily_costs) < 14:
        return None

    costs = [d.get("daily_cost", 0) or 0 for d in daily_costs]
    x = list(range(len(costs)))

    slope, intercept, r_squared, p_proxy = _linear_regression(x, costs)

    if slope > 0 and p_proxy < 0.05:
        return {
            "category": "anomaly",
            "severity": "medium",
            "title": "Upward cost trend detected",
            "description": f"Daily costs have been increasing at ${slope:.2f}/day over the analysis period. Projected monthly increase: ${slope * 30:,.2f}.",
            "current_state": f"Slope: ${slope:.2f}/day, R²: {r_squared:.3f}",
            "recommended_state": "Review recent changes to queries, datasets, or user base",
            "estimated_savings_monthly": 0,
            "confidence_score": r_squared,
            "metadata": {"slope": slope, "r_squared": r_squared, "p_value": p_proxy},
        }

    return None
