import io
import tokenize
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from app import web_links

BACKEND = Path(__file__).resolve().parents[2]
PROD_HOST = "https://my.minmatar.org"
# Files that may name the production site: settings defaults, the CORS
# default allow-list and an outbound User-Agent.
ALLOWED_FILES = {
    "app/cors.py",
    "app/settings.py",
    "app/settings_test.py",
    "app/settings_common.py",
    "campaigns/services/frontlines.py",
}


class WebLinksTest(SimpleTestCase):
    @override_settings(WEB_LINK_URL="https://staging.example/")
    def test_links_follow_the_setting(self):
        self.assertEqual(web_links.web_link(), "https://staging.example/")
        self.assertEqual(
            web_links.fleet_url(7), "https://staging.example/fleets/upcoming/7"
        )
        self.assertEqual(
            web_links.fleet_url("7", ended=True),
            "https://staging.example/fleets/history/7",
        )
        self.assertEqual(
            web_links.doctrine_url(3),
            "https://staging.example/ships/doctrines/list/3",
        )

    @override_settings(WEB_LINK_URL="https://staging.example")
    def test_discord_links_follow_the_setting(self):
        # pylint: disable=import-outside-toplevel
        from fleets.notifications import get_fleet_discord_notification

        message = get_fleet_discord_notification(
            fleet_id=5,
            fleet_type="strategic",
            fleet_location="Amamake",
            fleet_audience="Alliance",
            fleet_commander_name="FC",
            fleet_commander_id=1,
            fleet_description="Roam",
            fleet_voice_channel="Fleet 1",
            fleet_voice_channel_link=None,
        )
        urls = [
            button["url"]
            for row in message["components"]
            for button in row["components"]
            if button["url"].startswith("https://staging")
        ]
        self.assertIn("https://staging.example/fleets/history/5", urls)
        self.assertNotIn(PROD_HOST, str(message))

    def test_no_hard_coded_site_links(self):
        """Links to the website go through app.web_links, so dev and staging
        never link to production. A ``getattr(settings, "WEB_LINK_URL",
        <default>)`` fallback is allowed."""
        offenders = []
        for path in BACKEND.rglob("*.py"):
            rel = path.relative_to(BACKEND).as_posix()
            if (
                rel in ALLOWED_FILES
                or "/migrations/" in rel
                or "/tests/" in rel
                or "/management/" in rel
                or Path(rel).name.startswith("test")
            ):
                continue
            source = path.read_text(encoding="utf-8")
            if PROD_HOST not in source:
                continue
            lines = source.splitlines()
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            for token in tokens:
                if token.type != tokenize.STRING:
                    continue
                body = token.string.lstrip("rbfuRBFU").strip("\"'")
                if not body.startswith(PROD_HOST):
                    continue
                line = lines[token.start[0] - 1]
                if "WEB_LINK_URL" in line or "WEB_LINK_URL" in "".join(
                    lines[max(0, token.start[0] - 2) : token.start[0]]
                ):
                    continue
                offenders.append(f"{rel}:{token.start[0]}")
        self.assertEqual(offenders, [], "use app.web_links instead")
