def aria_sort_value(column: str, sort_key: str, sort_dir: int, sortable: set) -> str:
    """Return the appropriate ARIA sort attribute for a table header.

    Args:
        column: Identifier of the column being rendered.
        sort_key: Currently active sort column identifier.
        sort_dir: ``1`` for ascending, ``-1`` for descending.
        sortable: Set of column identifiers that support sorting.

    Returns:
        ``"ascending"``, ``"descending"`` or ``"none"``.
    """
    if column not in sortable:
        return "none"
    if column != sort_key:
        return "none"
    return "ascending" if sort_dir == 1 else "descending"
