from features.explore_bulk_select.selection_state import (
    get_aria_checked,
    get_indeterminate,
)


def test_aria_checked_none_selected():
    selected = set()
    total = 5
    assert get_aria_checked(selected, total) == "false"
    assert not get_indeterminate(selected, total)


def test_aria_checked_all_selected():
    selected = {1, 2, 3}
    total = 3
    assert get_aria_checked(selected, total) == "true"
    assert not get_indeterminate(selected, total)


def test_aria_checked_partial_selected():
    selected = {1, 2}
    total = 5
    assert get_aria_checked(selected, total) == "mixed"
    assert get_indeterminate(selected, total)


def test_total_zero_behaviour():
    selected = set()
    total = 0
    # With zero items there is nothing to select; treat as not selected.
    assert get_aria_checked(selected, total) == "false"
    assert not get_indeterminate(selected, total)
