import unittest

from features.profile_overview_scorebars.utils import compute_evidence_strength


class TestEvidenceStrength(unittest.TestCase):
    def test_normal_case(self):
        self.assertEqual(compute_evidence_strength(4, 5), 80)

    def test_zero_evidence(self):
        self.assertEqual(compute_evidence_strength(0, 0), 0)
        self.assertEqual(compute_evidence_strength(3, 0), 0)

    def test_rounding(self):
        # 1/3 = 33.33... should round to 33
        self.assertEqual(compute_evidence_strength(1, 3), 33)
        # 2/3 = 66.66... should round to 67
        self.assertEqual(compute_evidence_strength(2, 3), 67)


if __name__ == "__main__":
    unittest.main()
