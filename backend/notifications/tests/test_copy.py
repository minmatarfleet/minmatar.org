from django.test import SimpleTestCase, override_settings

from notifications.types.industry import (
    render_order_assignment,
    render_order_created,
    render_order_job,
)


@override_settings(WEB_LINK_URL="https://my.minmatar.org")
class FriendlyCopyTestCase(SimpleTestCase):
    def test_created_copy_is_plain(self):
        payload = render_order_created(
            {
                "order_id": 1,
                "public_short_code": "BTC",
                "needed_by": "2026-08-01",
                "items": ["5× Rifter", "2× Thrasher"],
                "location_name": "Amamake",
            }
        )
        self.assertEqual(payload["title"], "New Build Order BTC")
        self.assertNotIn("industry order", payload["title"].lower())
        discord = payload["discord_message"]
        self.assertIn("## New Build Order `BTC`", discord)
        self.assertIn("- 5× Rifter", discord)
        self.assertIn("- 2× Thrasher", discord)
        self.assertIn(
            "Want in? [Click here](https://my.minmatar.org/industry/orders/1/)",
            discord,
        )

    def test_assignment_copy_names_helpers(self):
        payload = render_order_assignment(
            {
                "order_id": 1,
                "public_short_code": "BTC",
                "item_id": 2,
                "assignment_id": 3,
                "item_name": "Rifter",
                "quantity": 5,
                "coordinators": [
                    {
                        "role": "blueprint",
                        "character_name": "Bob",
                        "eve_type_names": ["Rifter"],
                    }
                ],
            }
        )
        self.assertEqual(payload["title"], "You're on the order!")
        discord = payload["discord_message"]
        self.assertIn("You're on the order!", discord)
        self.assertIn("- 5× Rifter", discord)
        self.assertIn("**Who can help**", discord)
        self.assertIn("- Bob (can help with blueprints)", discord)
        self.assertIn(
            "click [here](https://my.minmatar.org/industry/orders/contract"
            "?order_id=1&item_id=2&assignment_id=3) for delivery.",
            discord,
        )
        self.assertNotIn("Coordinators", discord)

    def test_job_copy_skips_job_id_jargon(self):
        payload = render_order_job(
            {
                "order_id": 1,
                "public_short_code": "BTC",
                "item_id": 2,
                "assignment_id": 3,
                "item_name": "Rifter",
                "job_id": 424242,
            }
        )
        self.assertEqual(
            payload["title"], "We've detected an order blueprint cooking!"
        )
        discord = payload["discord_message"]
        self.assertIn("We've detected an order blueprint cooking!", discord)
        self.assertIn(
            "[click here](https://my.minmatar.org/industry/orders/contract"
            "?order_id=1&item_id=2&assignment_id=3) for delivery steps.",
            discord,
        )
        self.assertNotIn("424242", discord)
        self.assertNotIn("detected an industry", discord.lower())

    def test_created_copy_caps_long_item_lists(self):
        items = [f"{i}× Ship{i}" for i in range(1, 12)]
        payload = render_order_created(
            {
                "order_id": 1,
                "public_short_code": "BTC",
                "items": items,
            }
        )
        discord = payload["discord_message"]
        self.assertIn("- 1× Ship1", discord)
        self.assertIn("- 8× Ship8", discord)
        self.assertIn("- …and 3 more", discord)
        self.assertNotIn("- 9× Ship9", discord)
