"""Unit tests for the claim-evidence matrix and Tracxn benchmark mapping.

These import only the pure benchmark modules (stdlib-only) so they run without
the heavy application dependencies.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmarks.matrix import build_claim_evidence_matrix  # noqa: E402
from benchmarks.tracxn import (  # noqa: E402
    DIMENSIONS,
    benchmark_coverage,
    map_field_to_dimension,
)

_SAMPLE_RUN = {
    "company": "Acme Robotics",
    "run_id": 7,
    "verification": {
        "claims": [
            {"field": "funding", "value": "$12M Series A", "status": "verified",
             "evidence_url": "https://example.com/a", "confidence": 0.9, "note": "ok"},
            {"field": "hq", "value": "Munich", "status": "partial",
             "evidence_url": "", "confidence": 0.5, "note": "weak"},
            {"field": "reference_customer", "value": "Siemens", "status": "contradicted",
             "evidence_url": "https://example.com/c", "confidence": 0.2, "note": "no"},
        ]
    },
    "facts": [
        {"key": "hq", "value": "Munich, DE", "source_url": "https://example.com/hq"},
    ],
}


def test_map_field_to_dimension():
    assert map_field_to_dimension("funding") == "Funding & Investors"
    assert map_field_to_dimension("HQ") == "Location"
    assert map_field_to_dimension("reference_customer") == "Traction & Customers"
    assert map_field_to_dimension("nonsense") == "Other"


def test_benchmark_coverage_ratio():
    cov = benchmark_coverage(["funding", "hq", "reference_customer"])
    assert cov["coverage_ratio"] > 0
    assert cov["source"] == "https://tracxn.com"
    assert "Funding & Investors" in cov["covered"]
    assert len(cov["dimensions"]) == len(DIMENSIONS)


def test_build_matrix_shapes_and_verdicts():
    out = build_claim_evidence_matrix(_SAMPLE_RUN)
    assert out["startup"] == "Acme Robotics"
    assert out["summary"]["total_claims"] == 3
    assert out["summary"]["supported"] == 1
    assert out["summary"]["contradicted"] == 1
    verdicts = {r["field"]: r["verdict"] for r in out["matrix"]}
    assert verdicts["funding"] == "supported"
    assert verdicts["hq"] == "partially_supported"
    # Evidence URL falls back to a matching fact when the claim lacks one.
    hq_row = next(r for r in out["matrix"] if r["field"] == "hq")
    assert hq_row["evidence_url"] == "https://example.com/hq"


def test_empty_run_is_safe():
    out = build_claim_evidence_matrix({})
    assert out["summary"]["total_claims"] == 0
    assert out["matrix"] == []
