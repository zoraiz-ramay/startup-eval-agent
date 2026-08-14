import unittest

from features.evidence_tab.visibility import should_show_clear_button


class TestEvidenceTabVisibility(unittest.TestCase):
    def test_button_shown_for_nonempty_filter(self):
        self.assertTrue(should_show_clear_button("abc"))
        self.assertTrue(should_show_clear_button("  abc  "))

    def test_button_hidden_for_empty_or_whitespace(self):
        self.assertFalse(should_show_clear_button(""))
        self.assertFalse(should_show_clear_button("   "))
        self.assertFalse(should_show_clear_button("\n\t"))


if __name__ == "__main__":
    unittest.main()
