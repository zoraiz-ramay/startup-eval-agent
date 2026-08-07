import pytest
from features.claim_evidence_accessible_loading import get_aria_props

@pytest.mark.parametrize(
    "loading,error,expected",
    [
        (True, "", {"role": "status", "aria-live": "polite"}),
        (False, "Network error", {"role": "alert"}),
        (False, "", {}),
    ],
)
def test_get_aria_props(loading: bool, error: str, expected: dict):
    """Validate that ARIA properties are generated correctly for each state."""
    assert get_aria_props(loading, error) == expected
