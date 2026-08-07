"""Tracxn benchmark reference.

Tracxn (https://tracxn.com) is an established startup-intelligence platform. We
use the canonical dimensions it tracks per company as a benchmark: a credible
evaluation should present evidence across these dimensions. This module makes no
network calls - it encodes the benchmark schema and maps our internal claim
fields onto Tracxn's dimensions so reports can be scored for coverage.
"""
from __future__ import annotations

BENCHMARK_NAME = "Tracxn Startup Profile"
BENCHMARK_SOURCE = "https://tracxn.com"

# Canonical dimensions Tracxn tracks for a company profile.
DIMENSIONS = [
    "Sector & Market",
    "Founding Year",
    "Location",
    "Team & Founders",
    "Funding & Investors",
    "Business Model",
    "Product & Technology",
    "Traction & Customers",
    "Competition",
]

# Map internal claim/fact field names onto benchmark dimensions.
_FIELD_MAP = {
    "sector": "Sector & Market",
    "industry": "Sector & Market",
    "market": "Sector & Market",
    "founded": "Founding Year",
    "founded_year": "Founding Year",
    "year_founded": "Founding Year",
    "hq": "Location",
    "location": "Location",
    "headquarters": "Location",
    "founder": "Team & Founders",
    "founders": "Team & Founders",
    "ceo": "Team & Founders",
    "team": "Team & Founders",
    "funding": "Funding & Investors",
    "total_funding": "Funding & Investors",
    "investor": "Funding & Investors",
    "investors": "Funding & Investors",
    "business_model": "Business Model",
    "revenue": "Business Model",
    "pricing": "Business Model",
    "product": "Product & Technology",
    "technology": "Product & Technology",
    "reference_customer": "Traction & Customers",
    "customer": "Traction & Customers",
    "customers": "Traction & Customers",
    "traction": "Traction & Customers",
    "competitor": "Competition",
    "competitors": "Competition",
}


def map_field_to_dimension(field: str) -> str:
    """Return the Tracxn benchmark dimension for an internal field name."""
    key = (field or "").strip().lower().replace(" ", "_")
    if key in _FIELD_MAP:
        return _FIELD_MAP[key]
    for token, dim in _FIELD_MAP.items():
        if token in key:
            return dim
    return "Other"


def benchmark_coverage(fields: list) -> dict:
    """Given the claim fields present, report Tracxn benchmark coverage."""
    covered: list = []
    for f in fields:
        dim = map_field_to_dimension(f)
        if dim in DIMENSIONS and dim not in covered:
            covered.append(dim)
    missing = [d for d in DIMENSIONS if d not in covered]
    ratio = round(len(covered) / len(DIMENSIONS), 3) if DIMENSIONS else 0.0
    return {
        "benchmark": BENCHMARK_NAME,
        "source": BENCHMARK_SOURCE,
        "dimensions": list(DIMENSIONS),
        "covered": covered,
        "missing": missing,
        "coverage_ratio": ratio,
    }
