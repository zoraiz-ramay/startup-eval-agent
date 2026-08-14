def startup_permalink(origin: str, startup_id) -> str:
    """Return the absolute URL for a startup detail page.

    Parameters
    ----------
    origin: str
        The origin part of the URL, e.g. ``"https://app.example.com"``.
    startup_id: int | str
        The identifier of the startup.

    Returns
    -------
    str
        Fully qualified URL to the startup page.
    """
    # Ensure the origin does not end with a trailing slash to avoid double slashes.
    cleaned = origin.rstrip('/')
    return f"{cleaned}/startup/{startup_id}"
