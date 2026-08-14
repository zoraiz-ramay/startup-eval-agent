"""Unit tests for the evidence-cited employee time series and program prestige tiers.

Requires the application dependencies (pandas), so run in the app / Docker environment.
These exercise the pure sanitising/grading helpers in core/profile.py — no network or LLM.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.profile import _clean_employee_series, _program_tier_offline  # noqa: E402


def test_series_drops_uncited_points():
    pts = [
        {"year": 2022, "count": 20, "source_url": "https://a.com"},
        {"year": 2023, "count": 35, "source_url": ""},          # no source -> dropped
        {"year": 2024, "count": 50, "source_url": "https://b.com"},
    ]
    out = _clean_employee_series(pts)
    assert [p["year"] for p in out] == [2022, 2024]
    assert all(p["source_url"].startswith("http") for p in out)


def test_series_requires_two_points():
    one = [{"year": 2024, "count": 10, "source_url": "https://a.com"}]
    assert _clean_employee_series(one) == []


def test_series_dedupes_and_sorts():
    pts = [
        {"year": 2024, "count": 40, "source_url": "https://a.com"},
        {"year": 2022, "count": 10, "source_url": "https://b.com"},
        {"year": 2024, "count": 55, "source_url": "https://c.com"},   # higher count wins
    ]
    out = _clean_employee_series(pts)
    assert [p["year"] for p in out] == [2022, 2024]
    assert out[1]["count"] == 55


def test_series_rejects_implausible_values():
    pts = [
        {"year": 1990, "count": 10, "source_url": "https://a.com"},   # too old
        {"year": 2023, "count": -5, "source_url": "https://b.com"},   # negative
        {"year": 2023, "count": 12, "source_url": "https://c.com"},
        {"year": 2024, "count": 30, "source_url": "https://d.com"},
    ]
    out = _clean_employee_series(pts)
    assert [p["year"] for p in out] == [2023, 2024]


def test_program_tier_offline():
    assert _program_tier_offline("Y Combinator (W21)") == "tier1"
    assert _program_tier_offline("Siemens Xcelerator") == "tier1"
    assert _program_tier_offline("Microsoft for Startups") == "tier2"
    assert _program_tier_offline("Some Local Village Incubator") == "tier3"
