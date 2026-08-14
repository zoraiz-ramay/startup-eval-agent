from features.column_drawer_focus.utils import first_column_key


def test_first_column_key_nonempty():
    assert first_column_key(["a", "b", "c"]) == "a"


def test_first_column_key_empty():
    assert first_column_key([]) is None
