from django.test import SimpleTestCase

from notifications.discord_format import (
    discord_embed_from_payload,
    feature_color,
    feature_label,
)
from notifications.service import _render_payload
from notifications.types.industry import ORDER_CREATED
from notifications.types.tribes import TRIBE_MEMBERSHIP_REQUESTED


class DiscordFormatTestCase(SimpleTestCase):
    def test_feature_label_known(self):
        self.assertEqual(feature_label("industry"), "Industry")

    def test_feature_label_fallback(self):
        self.assertEqual(feature_label("fleet_ops"), "Fleet Ops")

    def test_embed_shows_industry_author(self):
        embed = discord_embed_from_payload(
            {
                "feature": "industry",
                "feature_label": "Industry",
                "title": "New Build Order BTC",
                "discord_message": (
                    "## New Build Order `BTC`\n"
                    "- 5× Rifter\n\n"
                    "Want in? [Click here](https://example.com/)"
                ),
                "url": "https://example.com/",
            }
        )
        self.assertEqual(embed["author"]["name"], "Industry")
        self.assertEqual(embed["color"], feature_color("industry"))
        self.assertIn("New Build Order", embed["description"])
        # Title already present in description — don't duplicate, and without
        # title Discord ignores embed.url so we omit it.
        self.assertNotIn("title", embed)
        self.assertNotIn("url", embed)

    def test_render_payload_stamps_feature(self):
        payload = _render_payload(
            ORDER_CREATED,
            {
                "order_id": 1,
                "public_short_code": "BTC",
                "items": ["1× Rifter"],
            },
        )
        self.assertEqual(payload["feature"], "industry")
        self.assertEqual(payload["feature_label"], "Industry")
        self.assertIn("discord_message", payload)

    def test_tribe_application_embed_says_it_once(self):
        payload = _render_payload(
            TRIBE_MEMBERSHIP_REQUESTED,
            {
                "group_name": "Mining",
                "tribe_name": "Industry",
                "applicant": "miner",
                "url": "https://example.com/alliance/tribes/1/2/members",
            },
        )
        embed = discord_embed_from_payload(payload)
        self.assertEqual(embed["author"]["name"], "Tribes")
        self.assertEqual(
            embed["description"],
            "**New tribe membership application** for **Mining** "
            "(Industry): miner has applied. Review it on the group's "
            "members page.",
        )
        # The bold first line already says it; no repeated embed title.
        self.assertNotIn("title", embed)
        button = payload["discord_components"][0]["components"][0]
        self.assertEqual(
            "https://example.com/alliance/tribes/1/2/members", button["url"]
        )

    def test_tribe_application_without_url_has_no_button(self):
        payload = _render_payload(
            TRIBE_MEMBERSHIP_REQUESTED,
            {
                "group_name": "Mining",
                "tribe_name": "Industry",
                "applicant": "m",
            },
        )
        self.assertNotIn("discord_components", payload)
        self.assertNotIn("admin panel", payload["discord_message"])
