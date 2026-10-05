"""BQ FinOps Agent configuration."""

from dataclasses import dataclass, field
import os
from typing import Optional


@dataclass(frozen=True)
class Config:
    """Agent configuration loaded from environment."""

    # GCP
    project_id: str = ""
    location: str = "us"
    credentials_path: Optional[str] = None

    # AI Providers
    gemini_api_key: str = ""
    claude_api_key: str = ""
    ai_model: str = "gemini-2.5-flash"

    # Analysis Parameters
    analysis_days_back: int = 30
    slot_analysis_hours_back: int = 168
    anomaly_stddev_threshold: float = 2.0

    # Storage
    staging_dataset: str = "finops_staging"
    recommendations_dataset: str = "finops_recommendations"

    # Notifications
    slack_webhook: str = ""
    teams_webhook: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables."""
        return cls(
            project_id=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
            location=os.environ.get("GOOGLE_LOCATION", "us"),
            credentials_path=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            claude_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            analysis_days_back=int(os.environ.get("ANALYSIS_DAYS_BACK", "30")),
            slot_analysis_hours_back=int(os.environ.get("SLOT_ANALYSIS_HOURS_BACK", "168")),
            anomaly_stddev_threshold=float(os.environ.get("ANOMALY_THRESHOLD_STDDEV", "2.0")),
            slack_webhook=os.environ.get("SLACK_WEBHOOK_URL", ""),
            teams_webhook=os.environ.get("TEAMS_WEBHOOK_URL", ""),
        )

    def validate(self) -> list[str]:
        """Return list of validation errors."""
        errors = []
        if not self.project_id:
            errors.append("GOOGLE_CLOUD_PROJECT not set")
        if not self.gemini_api_key and not self.claude_api_key:
            errors.append("Set GEMINI_API_KEY or ANTHROPIC_API_KEY")
        return errors
