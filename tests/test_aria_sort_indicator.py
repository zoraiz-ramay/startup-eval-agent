from features.aria_sort_indicator import aria_sort_value


def test_non_sortable_column():
    sortable = {"a", "b"}
    assert aria_sort_value("c", "a", 1, sortable) == "none"


def test_not_current_sort_column():
    sortable = {"a", "b"}
    assert aria_sort_value("a", "b", -1, sortable) == "none"


def test_ascending_sort():
    sortable = {"a"}
    assert aria_sort_value("a", "a", 1, sortable) == "ascending"


def test_descending_sort():
    sortable = {"b"}
    assert aria_sort_value("b", "b", -1, sortable) == "descending"
