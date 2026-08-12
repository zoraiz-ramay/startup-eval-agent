import unittest
from features.explore_row_permalink.util import startup_permalink


class TestStartupPermalink(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            startup_permalink('https://app.example.com', 42),
            'https://app.example.com/startup/42'
        )

    def test_trailing_slash(self):
        self.assertEqual(
            startup_permalink('https://app.example.com/', 'abc'),
            'https://app.example.com/startup/abc'
        )

    def test_origin_with_path(self):
        self.assertEqual(
            startup_permalink('https://app.example.com/v1', 7),
            'https://app.example.com/v1/startup/7'
        )


if __name__ == '__main__':
    unittest.main()
