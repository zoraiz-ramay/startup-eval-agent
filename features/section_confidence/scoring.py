"""Section confidence scoring.

Scoring rule derived only from existing structured signals:
- supported claim proportion in the section
- average source quality for cited evidence in the section
- presence of unsupported claims

Thresholds are intentionally explicit and deterministic:
- If a section has no evidence-backed claims, confidence is always ``low``.
- If any unsupported claim is present, confidence cannot be ``high``.
- ``high`` requires:
    * supported_claim_ratio >= 0.8
    * average_source_quality >= 0.7
    * no unsupported claims
    * evidence_backed_claim_count > 0
- ``medium`` requires:
    * evidence_backed_claim_count > 0
    * supported_claim_ratio >= 0.5
    * average_source_quality >= 0.4
    * otherwise unsupported claims may still be present
- All other cases are ``low``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, TypedDict

ConfidenceLabel = Literal["high", "medium", "low"]


class ConfidenceRationale(TypedDict):
    supported_claim_ratio: float
    average_source_quality: float
    unsupported_claims_present: bool
    evidence_backed_claim_count: int
    rule_applied: str


@dataclass(frozen=True)
class SectionSignals:
    """Structured inputs required to score a report section."""

    supported_claim_ratio: float
    average_source_quality: float
    unsupported_claims_present: bool
    evidence_backed_claim_count: int


@dataclass(frozen=True)
class SectionConfidenceResult:
    confidence: ConfidenceLabel
    rationale: ConfidenceRationale

    def as_dict(self) -> Dict[str, object]:
        return {
            "confidence": self.confidence,
            "rationale": dict(self.rationale),
        }


def _clamp(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _normalize(signals: SectionSignals) -> SectionSignals:
    return SectionSignals(
        supported_claim_ratio=_clamp(signals.supported_claim_ratio),
        average_source_quality=_clamp(signals.average_source_quality),
        unsupported_claims_present=bool(signals.unsupported_claims_present),
        evidence_backed_claim_count=max(0, signals.evidence_backed_claim_count),
    )


def score_section_confidence(signals: SectionSignals) -> SectionConfidenceResult:
    """Return deterministic confidence and machine-readable rationale."""

    normalized = _normalize(signals)
    applied_rules: List[str] = []

    if normalized.evidence_backed_claim_count == 0:
        applied_rules.append("no_evidence_backed_claims=>low")
        return SectionConfidenceResult(
            confidence="low",
            rationale={
                "supported_claim_ratio": normalized.supported_claim_ratio,
                "average_source_quality": normalized.average_source_quality,
                "unsupported_claims_present": normalized.unsupported_claims_present,
                "evidence_backed_claim_count": normalized.evidence_backed_claim_count,
                "rule_applied": ";".join(applied_rules),
            },
        )

    if normalized.unsupported_claims_present:
        applied_rules.append("unsupported_claims_present=>not_high")

    if (
        not normalized.unsupported_claims_present
        and normalized.supported_claim_ratio >= 0.8
        and normalized.average_source_quality >= 0.7
    ):
        applied_rules.append("ratio>=0.8_and_quality>=0.7_and_no_unsupported=>high")
        confidence: ConfidenceLabel = "high"
    elif (
        normalized.supported_claim_ratio >= 0.5
        and normalized.average_source_quality >= 0.4
    ):
        applied_rules.append("ratio>=0.5_and_quality>=0.4=>medium")
        confidence = "medium"
    else:
        applied_rules.append("below_medium_thresholds=>low")
        confidence = "low"

    return SectionConfidenceResult(
        confidence=confidence,
        rationale={
            "supported_claim_ratio": normalized.supported_claim_ratio,
            "average_source_quality": normalized.average_source_quality,
            "unsupported_claims_present": normalized.unsupported_claims_present,
            "evidence_backed_claim_count": normalized.evidence_backed_claim_count,
            "rule_applied": ";".join(applied_rules),
        },
    )
