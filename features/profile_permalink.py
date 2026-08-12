import os
from urllib.parse import urljoin


def build_permalink(startup_id: str) -> str:
    """Return the absolute permalink URL for a startup profile.

    The base origin is taken from the ``ORIGIN`` environment variable if set;
    otherwise ``http://localhost`` is used.  The resulting URL has the form
    ``{origin}/startup/{startup_id}``.

    Args:
        startup_id: The identifier of the startup.

    Returns:
        A fully‑qualified URL string.
    """
    origin = os.getenv("ORIGIN", "http://localhost")
    # Ensure the origin ends with a slash for correct joining
    if not origin.endswith("/"):
        origin += "/"
    return urljoin(origin, f"startup/{startup_id}")
