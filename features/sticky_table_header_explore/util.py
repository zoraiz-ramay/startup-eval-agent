def sticky_header_style() -> str:
    """Return CSS rules that make a table header sticky.

    The style targets <thead> cells within a table having the class
    ``dtable`` (as used by the Explore page) and sets ``position: sticky``
    with a top offset of ``0`` so the header sticks to the viewport when
    scrolling.
    """
    return (
        ".dtable thead th {"
        "position: sticky;"
        "top: 0;"
        "background: var(--bg, white);"
        "z-index: 2;"
        "}"
    )
