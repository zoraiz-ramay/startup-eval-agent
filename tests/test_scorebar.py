import unittest
from features.scorebar import clamp_score


class TestClampScore(unittest.TestCase):
    def test_normal_range(self):
        self.assertEqual(clamp_score(42), 42)
        self.assertEqual(clamp_score(0), 0)
        self.assertEqual(clamp_score(100), 100)

    def test_below_range(self):
        self.assertEqual(clamp_score(-5), 0)
        self.assertEqual(clamp_score(-0.1), 0)

    def test_above_range(self):
        self.assertEqual(clamp_score(150), 100)
        self.assertEqual(clamp_score(123.456), 100)

    def test_string_inputs(self):
        self.assertEqual(clamp_score("75"), 75)
        self.assertEqual(clamp_score("-20"), 0)
        self.assertEqual(clamp_score("200"), 100)
        self.assertEqual(clamp_score("not a number"), 0)


if __name__ == "__main__":
    unittest.main()
