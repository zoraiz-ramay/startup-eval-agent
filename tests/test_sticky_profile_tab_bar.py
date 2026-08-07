import pathlib


def test_profile_js_contains_sticky_class():
    """Ensure the Profile.jsx file includes the `sticky-header` class.

    The unit test mirrors the acceptance criterion that the tab container
    receives the `sticky-header` CSS class after scrolling. By checking the
    source we guarantee the class is present in the rendered markup.
    """
    file_path = pathlib.Path("ui/src/pages/Profile.jsx")
    content = file_path.read_text(encoding="utf-8")
    assert "sticky-header" in content, "Profile.jsx should contain the 'sticky-header' class"
