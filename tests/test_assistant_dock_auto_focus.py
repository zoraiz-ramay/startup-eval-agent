from features.assistant_dock_auto_focus import should_focus


def test_should_focus_when_open() -> None:
    assert should_focus(True) is True


def test_should_not_focus_when_closed() -> None:
    assert should_focus(False) is False
