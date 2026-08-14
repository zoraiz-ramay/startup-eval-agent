import unittest

from features.column_reorder import is_move_up_disabled, is_move_down_disabled


class TestColumnReorderUtilities(unittest.TestCase):
    def test_move_up_disabled(self) -> None:
        self.assertTrue(is_move_up_disabled(0, 5))
        self.assertFalse(is_move_up_disabled(1, 5))
        self.assertFalse(is_move_up_disabled(4, 5))
        # Edge case: single column list – both directions disabled
        self.assertTrue(is_move_up_disabled(0, 1))

    def test_move_down_disabled(self) -> None:
        self.assertTrue(is_move_down_disabled(4, 5))
        self.assertFalse(is_move_down_disabled(3, 5))
        self.assertFalse(is_move_down_disabled(0, 5))
        # Edge case: single column list – both directions disabled
        self.assertTrue(is_move_down_disabled(0, 1))

    def test_consistency(self) -> None:
        length = 7
        for i in range(length):
            up = is_move_up_disabled(i, length)
            down = is_move_down_disabled(i, length)
            if i == 0:
                self.assertTrue(up)
                self.assertFalse(down)
            elif i == length - 1:
                self.assertFalse(up)
                self.assertTrue(down)
            else:
                self.assertFalse(up)
                self.assertFalse(down)


if __name__ == "__main__":
    unittest.main()
