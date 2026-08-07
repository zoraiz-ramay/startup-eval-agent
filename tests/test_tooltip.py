from utils import tooltip


def test_get_evidence_tooltip() -> None:
    """Ensure the tooltip helper returns the expected explanatory string."""
    assert tooltip.get_evidence_tooltip() == "Verified facts / total evidence"
