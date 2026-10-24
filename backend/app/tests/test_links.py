import io
import tokenize
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from app import links

BACKEND = Path(__file__).resolve().parents[2]
PROD_HOST = "https://my.minmatar.org"
# Files that may name the production site: settings defaults, the CORS
# default allow-list and an outbound User-Agent.
ALLOWED_FILES = {
    "app/cors.py",
    "app/links.py",
    "app/settings.py",
    "app/settings_test.py",
    "app/settings_common.py",
    "campaigns/services/frontlines.py",
}


PAGES = BACKEND.parent / "frontend" / "app" / "src" / "pages"
# Website pages other surfaces link to, and the Astro page that serves each.
# Released desktop versions keep opening theirs (desktop/src/main/
# web_routes.js), so a page that moves must leave a redirect behind.
LINKED_PAGES = {
    # Desktop
    "/fleets/upcoming/<id>": "fleets/upcoming/[fleet_id].astro",
    "/fleets/history/<id>": "fleets/history/[fleet_id].astro",
    "/ships/srp/killmails/": "ships/srp/killmails.astro",
    "/campaigns/<slug>": "campaigns/[slug]/index.astro",
    "/intel/scans/<id>": "intel/scans/[report_id].astro",
    # Backend (app/links.py)
    "/fleets/upcoming/": "fleets/upcoming.astro",
    "/fleets/upcoming/edit/<id>": "fleets/upcoming/edit/[fleet_id].astro",
    "/ships/fittings/<id>": "ships/fittings/[fitting_id].astro",
    "/ships/doctrines/list/<id>": "ships/doctrines/list/[doctrine_id].astro",
    "/learning/guides/<name>/": "learning/guides/[name].astro",
}


class LinksTest(SimpleTestCase):
    @override_settings(WEB_LINK_URL="https://staging.example/")
    def test_links_follow_the_setting(self):
        self.assertEqual(links.site_url("/"), "https://staging.example/")
        self.assertEqual(
            links.fleet_url(7), "https://staging.example/fleets/upcoming/7"
        )
        self.assertEqual(
            links.fleet_url("7", ended=True),
            "https://staging.example/fleets/history/7",
        )
        self.assertEqual(
            links.doctrine_url(3),
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

    def test_linked_pages_exist(self):
        if not PAGES.exists():  # a backend-only checkout
            self.skipTest("frontend not checked out")
        missing = [
            route
            for route, page in LINKED_PAGES.items()
            if not (PAGES / page).exists()
        ]
        self.assertEqual(missing, [], "keep or redirect these routes")

    def test_no_hard_coded_site_links(self):
        """Links to the website go through app.links, so dev and staging
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
        self.assertEqual(offenders, [], "use app.links instead")
