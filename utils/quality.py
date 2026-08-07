def get_quality_color(quality: str) -> str:
    """Return a background color for a given source quality.

    Known qualities are "high", "medium", and "low" which map to
    green, orange, and red respectively. Unknown values return "gray".
    """
    mapping = {"high": "green", "medium": "orange", "low": "red"}
    return mapping.get(quality.lower(), "gray")
