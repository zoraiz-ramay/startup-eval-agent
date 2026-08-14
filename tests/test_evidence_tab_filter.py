import unittest
from features.evidence_tab.filter_utils import (
    filter_evidence,
    is_empty_after_filter,
)


class TestEvidenceTabFilter(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = [
            {"id": 1, "title": "Alpha"},
            {"id": 2, "title": "Beta"},
        ]

    def test_filter_matches(self) -> None:
        filtered = filter_evidence(self.evidence, "alpha")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], 1)

    def test_filter_no_match(self) -> None:
        filtered = filter_evidence(self.evidence, "gamma")
        self.assertEqual(filtered, [])
        self.assertTrue(is_empty_after_filter(self.evidence, "gamma"))

    def test_empty_filter_returns_all(self) -> None:
        filtered = filter_evidence(self.evidence, "")
        self.assertEqual(filtered, self.evidence)
        self.assertFalse(is_empty_after_filter(self.evidence, ""))


if __name__ == "__main__":
    unittest.main()
