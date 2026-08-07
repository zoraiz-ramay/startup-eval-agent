import unittest
from utils import quality


class TestQualityColor(unittest.TestCase):
    def test_known_qualities(self):
        self.assertEqual(quality.get_quality_color("high"), "green")
        self.assertEqual(quality.get_quality_color("Medium"), "orange")
        self.assertEqual(quality.get_quality_color("LOW"), "red")

    def test_unknown_quality(self):
        self.assertEqual(quality.get_quality_color("unknown"), "gray")


if __name__ == "__main__":
    unittest.main()
