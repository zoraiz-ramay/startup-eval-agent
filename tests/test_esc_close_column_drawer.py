import pathlib


def test_explore_drawer_escape_listener_exists():
    """Ensure the Escape key listener is added to the Explore component."""
    # Resolve the path relative to the repo root
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    file_path = repo_root / "ui" / "src" / "pages" / "Explore.jsx"
    content = file_path.read_text(encoding="utf-8")
    # Simple sanity check: look for the key check handling Escape
    assert 'if (e.key === "Escape")' in content, "Escape key handler not found in Explore.jsx"
