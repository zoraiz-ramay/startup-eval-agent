from typing import Set

from features.keyboard_sortable_explore.aria_sort import compute_aria_sort


def test_compute_aria_sort_not_sortable() -> None:
    sortable: Set[str] = {"a", "b"}
    assert compute_aria_sort("c", "a", 1, sortable) == "none"


def test_compute_aria_sort_sortable_not_active() -> None:
    sortable: Set[str] = {"a", "b"}
    assert compute_aria_sort("a", "b", 1, sortable) == "none"


def test_compute_aria_sort_active_ascending() -> None:
    sortable: Set[str] = {"a", "b"}
    assert compute_aria_sort("a", "a", 1, sortable) == "ascending"


def test_compute_aria_sort_active_descending() -> None:
    sortable: Set[str] = {"a", "b"}
    assert compute_aria_sort("b", "b", -1, sortable) == "descending"
