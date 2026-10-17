from django.test import TestCase

from notifications.discord_buttons import (
    ack_custom_id,
    mark_as_read_components,
)


class DiscordButtonsTestCase(TestCase):
    def test_ack_custom_id_format(self):
        self.assertEqual(ack_custom_id(42), "notif_ack:42")

    def test_mark_as_read_components(self):
        components = mark_as_read_components(99)
        self.assertEqual(len(components), 1)
        button = components[0]["components"][0]
        self.assertEqual(button["label"], "Mark as read")
        self.assertEqual(button["custom_id"], "notif_ack:99")
        self.assertEqual(button["style"], 2)
