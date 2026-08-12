def get_aria_label(copied: bool, company: str) -> str:
    """Return the appropriate ARIA label for a copy‑link button.

    Args:
        copied: ``True`` if the link has just been copied, otherwise ``False``.
        company: The company name associated with the link.

    Returns:
        A string suitable for the button's ``aria-label`` attribute.
    """
    if not company:
        return ""
    return f"Link for {company} copied" if copied else f"Copy link to {company}"
