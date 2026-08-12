from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


SUPPORTED_TOPICS = {
    "founding_year",
    "headquarters",
    "funding_total",
    "employee_count",
    "pricing",
    "launch_date",
}


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    title: str = ""
    url: str = ""
    quality_score: Optional[float] = None


@dataclass(frozen=True)
class Claim:
    topic: str
    entity: str
    value: str
    section: str
    source: SourceRef


@dataclass(frozen=True)
class ValueComparison:
    raw_value: str
    normalized_value: Any
    source: SourceRef


@dataclass(frozen=True)
class Contradiction:
    topic: str
    entity: str
    section: str
    values: list[ValueComparison] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "entity": self.entity,
            "section": self.section,
            "values": [
                {
                    "raw_value": item.raw_value,
                    "normalized_value": item.normalized_value,
                    "source_id": item.source.source_id,
                    "source_title": item.source.title,
                    "source_url": item.source.url,
                    "source_quality_score": item.source.quality_score,
                }
                for item in self.values
            ],
        }
