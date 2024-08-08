import unittest
from unittest.mock import Mock

from core import make_nickname

class TestCategorizeByAge(unittest.TestCase):
    def test_basic_nickname(self):
        character = Mock(character_name="Bob", corporation=Mock(ticker="ABC"))
        discord = Mock(is_down_under=False, dress_wearer=False)
        self.assertEqual(f"[ABC] Bob", make_nickname(character, discord))

    def test_down_under_nickname(self):
        character = Mock(character_name="Bob", corporation=Mock(ticker="ABC"))
        discord = Mock(is_down_under=True, dress_wearer=False)
        self.assertEqual(f"qoᗺ [ƆᗺⱯ]", make_nickname(character, discord))

    def test_dress_wearer(self):
        character = Mock(character_name="Bob", corporation=Mock(ticker="ABC"))
        discord = Mock(is_down_under=False, dress_wearer=True)
        self.assertEqual(f"[👗] Bob", make_nickname(character, discord))

    def test_dry_corp(self):
        character = Mock(character_name="Scott", corporation=Mock(ticker="-DRY-"))
        discord = Mock(is_down_under=False, dress_wearer=True)
        self.assertEqual(f"[ω] Scott", make_nickname(character, discord))

if __name__ == "__main__":
    unittest.main()