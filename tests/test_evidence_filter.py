import pytest
from features.evidence_filter import filter_facts


@pytest.fixture
def sample_facts():
    return [
        {"key": "Revenue", "value": "10M", "method": "estimate"},
        {"key": "Employees", "value": "50", "method": "public"},
        {"key": "Founded", "value": "2015", "method": "website"},
    ]


def test_filter_facts_no_query(sample_facts):
    assert filter_facts(sample_facts, "") == sample_facts


def test_filter_facts_matches_key(sample_facts):
    result = filter_facts(sample_facts, "revenue")
    assert len(result) == 1
    assert result[0]["key"] == "Revenue"


def test_filter_facts_matches_method(sample_facts):
    result = filter_facts(sample_facts, "public")
    assert len(result) == 1
    assert result[0]["key"] == "Employees"


def test_filter_facts_case_insensitive(sample_facts):
    result = filter_facts(sample_facts, "FoUnDeD")
    assert len(result) == 1
    assert result[0]["key"] == "Founded"
