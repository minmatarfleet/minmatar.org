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
                "items_summary": "5× Rifter",
                "location_name": "Amamake",
            }
        )
        self.assertIn("New build order", payload["title"])
        self.assertNotIn("industry order", payload["title"].lower())
        self.assertIn("claim", payload["body"].lower())
        self.assertIn("due Aug 1", payload["body"])

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
        self.assertIn("You're building", payload["title"])
        self.assertIn("hand it in", payload["body"].lower())
        self.assertIn("can help with blueprints", payload["discord_message"])
        self.assertNotIn("Coordinators", payload["discord_message"])

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
        self.assertEqual(payload["title"], "Rifter is cooking")
        self.assertNotIn("424242", payload["discord_message"])
        self.assertNotIn("detected", payload["body"].lower())
        self.assertIn("hand it in", payload["body"].lower())
