"""Data models for recommendations."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(str, Enum):
    SLOT_OPTIMIZATION = "slot_optimization"
    QUERY_PATTERN = "query_pattern"
    ANOMALY = "anomaly"
    SCHEMA_OPTIMIZATION = "schema_optimization"
    COST_ALLOCATIONS = "cost_allocations"


class Status(str, Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IMPLEMENTED = "implemented"
    IGNORED = "ignored"


@dataclass
class Recommendation:
    """A cost optimization recommendation."""

    category: Category
    severity: Severity
    title: str
    description: str
    current_state: str
    recommended_state: str
    estimated_savings_monthly: float
    confidence_score: float  # 0.0 to 1.0
    sql_code: Optional[str] = None
    job_id: Optional[str] = None
    dataset_id: Optional[str] = None
    table_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: Status = Status.NEW
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "current_state": self.current_state,
            "recommended_state": self.recommended_state,
            "estimated_savings_monthly": self.estimated_savings_monthly,
            "confidence_score": self.confidence_score,
            "sql_code": self.sql_code,
            "job_id": self.job_id,
            "dataset_id": self.dataset_id,
            "table_id": self.table_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Recommendation":
        """Create from dictionary."""
        return cls(
            category=Category(data["category"]),
            severity=Severity(data["severity"]),
            title=data["title"],
            description=data["description"],
            current_state=data["current_state"],
            recommended_state=data["recommended_state"],
            estimated_savings_monthly=data.get("estimated_savings_monthly", 0.0),
            confidence_score=data.get("confidence_score", 0.5),
            sql_code=data.get("sql_code"),
            job_id=data.get("job_id"),
            dataset_id=data.get("dataset_id"),
            table_id=data.get("table_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            status=Status(data.get("status", "new")),
            metadata=data.get("metadata", {}),
        )

    @property
    def total_savings_yearly(self) -> float:
        """Calculate estimated yearly savings."""
        return self.estimated_savings_monthly * 12
