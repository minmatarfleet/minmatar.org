import json

from django.test import SimpleTestCase

from eveonline.helpers.killmail_text import (
    MAX_LITERAL_CHARS,
    dump_killmail_list,
    json_to_repr_text,
    load_killmail_list,
    parse_killmail_list,
    repr_to_json_text,
)

ROWS = [
    {
        "character_id": None,
        "final_blow": True,
        "damage_done": 12,
        "name": "O'Brien é",
        "security_status": -1.5,
        "items": [{"flag": 5, "items": None}],
    }
]


class KillmailTextTest(SimpleTestCase):
    def test_reads_old_repr_rows(self):
        self.assertEqual(parse_killmail_list(str(ROWS)), ROWS)

    def test_reads_json_rows(self):
        self.assertEqual(parse_killmail_list(dump_killmail_list(ROWS)), ROWS)

    def test_empty_and_none_text(self):
        for text in (None, "", "None", "null", "[]"):
            self.assertEqual(parse_killmail_list(text), [])

    def test_malformed_text_is_empty_not_an_error(self):
        for text in (
            "list of attackers",
            "[{'a': 1",
            "__import__('os').system('true')",
            "{'not': 'a list'}",
            "[" * 100000,
        ):
            self.assertEqual(parse_killmail_list(text), [])
            self.assertIsNone(load_killmail_list(text))

    def test_oversized_text_is_not_evaluated(self):
        text = "[" + "1," * MAX_LITERAL_CHARS + "]"
        text = text.replace("1,", "None,", 1)  # not JSON, so literal path
        self.assertIsNone(load_killmail_list(text))

    def test_repr_round_trips_through_json_and_back(self):
        old = str(ROWS)
        new = repr_to_json_text(old)
        self.assertEqual(json.loads(new), ROWS)
        self.assertEqual(json_to_repr_text(new), old)

    def test_conversion_skips_json_and_unreadable_rows(self):
        self.assertIsNone(repr_to_json_text(dump_killmail_list(ROWS)))
        self.assertIsNone(repr_to_json_text("list of attackers"))
        self.assertIsNone(json_to_repr_text(str(ROWS)))
