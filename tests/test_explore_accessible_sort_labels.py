import pytest
from features.explore_accessible_sort_labels import generate_aria_label

@pytest.mark.parametrize(
    "col_label,is_current,direction,expected",
    [
        ("Fit Score", True, 1, "Sorted by Fit Score ascending"),
        ("Fit Score", True, -1, "Sorted by Fit Score descending"),
        ("Fit Score", False, 1, "Sort by Fit Score ascending"),
        ("Company", False, -1, "Sort by Company ascending"),
    ],
)
def test_generate_aria_label(col_label, is_current, direction, expected):
    assert generate_aria_label(col_label, is_current, direction) == expected
