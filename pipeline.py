"""Run the full analysis pipeline."""

import logging
from datetime import datetime
from typing import Optional

from config import Config
from collectors.bq_jobs import get_query_fingerprints, get_top_cost_queries, get_table_stats
from collectors.monitoring import get_reservation_utilization
from collectors.billing import get_daily_cost
from analyzers.slot_health import analyze_slot_health
from analyzers.query_patterns import analyze_query_patterns
from analyzers.anomaly_detector import detect_cost_anomalies, detect_trend_anomaly
from analyzers.optimization_scan import scan_schema_optimizations
from agents.gemini_agent import GeminiAgent
from models.storage import BQStorage

logger = logging.getLogger(__name__)


class FinOpsAgent:
    """Main agent that orchestrates the FinOps analysis pipeline."""

    def __init__(self, config: Config):
        self.config = config
        self.storage = BQStorage(config.project_id, config.location)
        self.agent = None

        if config.gemini_api_key:
            self.agent = GeminiAgent(
                api_key=config.gemini_api_key,
                model=config.ai_model,
            )

    def run(self) -> list[dict]:
        """Run the full analysis pipeline."""
        logger.info("Starting FinOps analysis for project: %s", self.config.project_id)

        all_recommendations = []

        # Step 1: Collect data
        logger.info("Step 1: Collecting data...")
        with self.storage.client.connection() as conn:
            # BQ Jobs
            fingerprints = get_query_fingerprints(
                self.config.project_id,
                self.config.location,
                self.config.analysis_days_back,
            )
            top_queries = get_top_cost_queries(
                self.config.project_id,
                self.config.location,
                self.config.analysis_days_back,
            )
            table_stats = get_table_stats(
                self.config.project_id,
                self.config.location,
                self.config.analysis_days_back,
            )

            # Monitoring
            slot_util = get_reservation_utilization(
                self.config.project_id,
                self.config.slot_analysis_hours_back,
            )

            # Billing
            daily_costs = get_daily_cost(
                self.config.project_id,
                days_back=self.config.analysis_days_back,
            )

        # Step 2: Analyze
        logger.info("Step 2: Running analysis...")

        # Slot health
        slot_recs = analyze_slot_health(
            slot_util.get("reservations", []),
            [],  # Would need reservation details
        )
        all_recommendations.extend(slot_recs)

        # Query patterns
        query_recs = analyze_query_patterns(fingerprints)
        all_recommendations.extend(query_recs)

        # Anomalies
        anomaly_recs = detect_cost_anomalies(
            daily_costs,
            self.config.anomaly_stddev_threshold,
        )
        trend_rec = detect_trend_anomaly(daily_costs)
        if trend_rec:
            anomaly_recs.append(trend_rec)
        all_recommendations.extend(anomaly_recs)

        # Schema optimizations
        schema_recs = scan_schema_optimizations(table_stats)
        all_recommendations.extend(schema_recs)

        # Step 3: AI analysis
        logger.info("Step 3: Running AI analysis...")
        ai_summary = None
        if self.agent and all_recommendations:
            ai_summary = self.agent.analyze_recommendations(all_recommendations)

        # Step 4: Store
        logger.info("Step 4: Storing results...")
        saved = self.storage.save_recommendations(all_recommendations)
        logger.info("Saved %d recommendations", saved)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_recommendations": len(all_recommendations),
            "total_monthly_savings": sum(r.get("estimated_savings_monthly", 0) for r in all_recommendations),
            "saved_count": saved,
            "ai_summary": ai_summary,
            "recommendations": all_recommendations,
        }
