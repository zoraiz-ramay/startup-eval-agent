import pytest

from features.keyboard_nav.util import is_activation_key


@pytest.mark.parametrize(
    "key,expected",
    [
        ("Enter", True),
        (" ", True),
        ("Spacebar", False),
        ("Escape", False),
        ("a", False),
    ],
)
def test_is_activation_key(key: str, expected: bool) -> None:
    assert is_activation_key(key) == expected
