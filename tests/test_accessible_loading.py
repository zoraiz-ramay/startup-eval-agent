import pathlib
import re


def test_loading_component_has_aria_live():
    """Ensure the Loading component includes aria-live='polite'."""
    file_path = pathlib.Path(__file__).parents[1] / "ui" / "src" / "components" / "widgets.jsx"
    content = file_path.read_text(encoding="utf-8")
    # Find the Loading component definition
    pattern = r"export\s+function\s+Loading\s*\([^)]*\)\s*{[^}]*}"  # noqa: W605
    match = re.search(pattern, content, re.DOTALL)
    assert match is not None, "Loading component not found in widgets.jsx"
    comp_body = match.group(0)
    # Check for aria-live attribute on the <p> element
    assert re.search(r"<p[^>]*aria-live\s*=\s*['\"]polite['\"]", comp_body), (
        "Loading component missing aria-live='polite' attribute"
    )
