import pytest

from features.company_name_sort_accessibility.aria import aria_sort


def test_aria_sort_not_sortable():
    # Column not in the sortable set should always return "none"
    assert aria_sort("foo", "foo", 1, {"bar", "baz"}) == "none"


def test_aria_sort_not_current_column():
    sortable = {"company", "final_score"}
    # "company" is sortable but not the active sort column
    assert aria_sort("company", "final_score", 1, sortable) == "none"


@pytest.mark.parametrize(
    "direction,expected",
    [(1, "ascending"), (-1, "descending")],
)
def test_aria_sort_current_column(direction, expected):
    sortable = {"company"}
    assert aria_sort("company", "company", direction, sortable) == expected
