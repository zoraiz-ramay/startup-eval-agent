import re
from pathlib import Path


def test_error_div_has_role_alert() -> None:
    """Ensure the Alerts component error div includes role='alert'."""
    alerts_path = Path(__file__).parent / "ui" / "src" / "pages" / "Alerts.jsx"
    content = alerts_path.read_text(encoding="utf-8")
    pattern = r"<div\s+className=[\"']error-box[\"']\s+role=[\"']alert[\"']>"
    assert re.search(pattern, content), "Error div should have role='alert'"
