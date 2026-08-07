"""Tests for evidence‑filter utility functions."""

import unittest

from features.evidence_filter.utils import should_show_clear_button


class TestShouldShowClearButton(unittest.TestCase):
    def test_empty_string(self) -> None:
        self.assertFalse(should_show_clear_button(""))

    def test_whitespace_string(self) -> None:
        # Whitespace counts as characters, so button should appear
        self.assertTrue(should_show_clear_button(" "))

    def test_non_empty(self) -> None:
        self.assertTrue(should_show_clear_button("abc"))


if __name__ == "__main__":
    unittest.main()
