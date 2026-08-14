import unittest

from features.copy_link_feedback import copy_feedback_message


class TestCopyLinkFeedback(unittest.TestCase):
    def test_standard_company(self) -> None:
        self.assertEqual(
            copy_feedback_message("Acme Corp"), "Link for Acme Corp copied"
        )

    def test_empty_company(self) -> None:
        self.assertEqual(copy_feedback_message(""), "Link for  copied")

    def test_whitespace_company(self) -> None:
        self.assertEqual(copy_feedback_message("   "), "Link for  copied")

    def test_non_string_input(self) -> None:
        # The function expects a string; passing a non‑string should raise.
        with self.assertRaises(AttributeError):
            # type: ignore[arg-type]
            copy_feedback_message(123)  # noqa: E501


if __name__ == "__main__":
    unittest.main()
