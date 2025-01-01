import unittest
from datetime import datetime

from structures.helpers import (
    get_skyhook_details,
    get_structure_details,
    StructureResponse,
)


class StructureHelperTest(unittest.TestCase):

    def test_get_skyhook_details(self):
        selected_item_window = "Orbital Skyhook (KBP7-G III) [Sukanan Inititive]\n0.5 AU\nReinforced until 2024.07.17 11:10:47"
        expected = StructureResponse(
            structure_name="Orbital Skyhook",
            location="KBP7-G III",
            # "owner": "Sukanan Inititive",
            timer=datetime.strptime(
                "2024.07.17 11:10:47", "%Y.%m.%d %H:%M:%S"
            ),
        )
        self.assertEqual(get_skyhook_details(selected_item_window), expected)

    def test_get_structure_details(self):
        selected_item_window = (
            "Sosala - WATERMELLON\n0 m\nReinforced until 2024.06.23 23:20:58"
        )
        expected = StructureResponse(
            location="Sosala",
            structure_name="WATERMELLON",
            timer=datetime.strptime(
                "2024.06.23 23:20:58", "%Y.%m.%d %H:%M:%S"
            ),
        )
        self.assertEqual(get_structure_details(selected_item_window), expected)

    def test_anchoring_structure(self):
        selected_item_window = (
            "Sosala - WATERMELLON\n0 m\nAnchoring until 2024.06.23 23:20:58"
        )
        expected = StructureResponse(
            location="Sosala",
            structure_name="WATERMELLON",
            timer=datetime.strptime(
                "2024.06.23 23:20:58", "%Y.%m.%d %H:%M:%S"
            ),
        )
        self.assertEqual(get_structure_details(selected_item_window), expected)
