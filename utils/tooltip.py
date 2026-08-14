def get_evidence_tooltip() -> str:
    """Return the tooltip text that explains the Evidence Strength metric.

    The application displays an info icon next to the **Evidence Strength** column
    header.  Screen readers announce the ``aria-label`` of that icon, and browsers
    show the ``title`` attribute as a hover tooltip.  Keeping the text in a single
    function makes it reusable and easy to test.
    """
    return "Verified facts / total evidence"
