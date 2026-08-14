"""Pure stdlib contradiction detection utilities."""

from .detector import detect_contradictions
from .models import Claim, Contradiction, SourceRef, ValueComparison
from .normalization import normalize_claim_value

__all__ = [
    "Claim",
    "Contradiction",
    "SourceRef",
    "ValueComparison",
    "detect_contradictions",
    "normalize_claim_value",
]
