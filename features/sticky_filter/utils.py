def get_sticky_style() -> dict:
    """Return the inline CSS style dictionary for the sticky filter bar.

    The style mirrors the requirements:
        position: sticky,
        top: 0,
        z-index: 5,
        background: var(--bg)
    """
    return {
        "position": "sticky",
        "top": 0,
        "zIndex": 5,
        "background": "var(--bg)"
    }
