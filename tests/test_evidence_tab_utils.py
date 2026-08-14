import pytest

from features.evidence_tab.utils import filter_evidence


@pytest.fixture
def sample_data():
    return [
        {"id": 1, "title": "Alpha", "description": "First item"},
        {"id": 2, "title": "Beta", "description": "Second item"},
        {"id": 3, "title": "Gamma", "description": "Third item"},
    ]


def test_no_query_returns_original(sample_data):
    result = filter_evidence(sample_data, "")
    assert result == sample_data


def test_query_matches_title(sample_data):
    result = filter_evidence(sample_data, "beta")
    assert len(result) == 1
    assert result[0]["title"] == "Beta"


def test_query_is_case_insensitive(sample_data):
    result = filter_evidence(sample_data, "ALPHA")
    assert len(result) == 1
    assert result[0]["title"] == "Alpha"


def test_query_matches_any_field(sample_data):
    result = filter_evidence(sample_data, "third")
    assert len(result) == 1
    assert result[0]["title"] == "Gamma"


def test_query_no_match_returns_empty(sample_data):
    result = filter_evidence(sample_data, "delta")
    assert result == []
