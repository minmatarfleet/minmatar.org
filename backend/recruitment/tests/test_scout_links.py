from django.contrib.auth.models import Permission
from django.test import Client

from app.test import TestCase
from recruitment.models import ScoutOutreach, ScoutOutreachClick
from recruitment.scout_links import hash_visitor, is_bot, outreach_stats

BASE_URL = "/api/recruitment/scout"
THREAD = "https://www.reddit.com/r/evejobs/comments/1abc234/lf_corp_eutz/"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0 Safari/537.36"
)


class ScoutLinksTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def grant_scout(self):
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_scoutoutreach")
        )

    def register(self, thread_url=THREAD, **extra):
        payload = {
            "surface": "evejobs",
            "thread_url": thread_url,
            "prospect": "u/newbro",
            "seat": "BNSQ",
            **extra,
        }
        return self.client.post(
            f"{BASE_URL}/outreach",
            payload,
            content_type="application/json",
            **self.auth,
        )

    def click(self, code, target="discord", ip="203.0.113.7", ua=BROWSER):
        return self.client.post(
            f"{BASE_URL}/clicks",
            {
                "code": code,
                "target": target,
                "client_ip": ip,
                "user_agent": ua,
            },
            content_type="application/json",
        )


class RegisterOutreachTestCase(ScoutLinksTestCase):
    def test_requires_scout_feature(self):
        self.assertEqual(403, self.register().status_code)
        self.assertFalse(ScoutOutreach.objects.exists())

    def test_returns_code_and_link_base(self):
        self.grant_scout()
        response = self.register()
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertRegex(body["code"], r"^[a-z2-9]{6}$")
        self.assertEqual(
            f"https://my.minmatar.org/go/{body['code']}/", body["link_base"]
        )
        outreach = ScoutOutreach.objects.get()
        self.assertEqual("BNSQ", outreach.seat)
        self.assertEqual(self.user, outreach.created_by)

    def test_same_thread_reuses_code(self):
        self.grant_scout()
        first = self.register().json()
        second = self.register(seat="L3ARN", surface="forums").json()
        self.assertEqual(first["code"], second["code"])
        self.assertEqual("L3ARN", second["seat"])
        self.assertEqual(1, ScoutOutreach.objects.count())

    def test_rejects_non_url_thread(self):
        self.grant_scout()
        self.assertEqual(400, self.register("not a url").status_code)

    def test_superuser_needs_no_grant(self):
        self.make_superuser()
        self.assertEqual(200, self.register().status_code)


class RecordClickTestCase(ScoutLinksTestCase):
    def setUp(self):
        super().setUp()
        self.outreach = ScoutOutreach.objects.create(
            code="k3x9qa", surface="evejobs", thread_url=THREAD
        )

    def test_records_click_without_storing_ip(self):
        self.assertEqual(201, self.click("k3x9qa").status_code)
        click = ScoutOutreachClick.objects.get()
        self.assertEqual("discord", click.target)
        self.assertFalse(click.is_bot)
        self.assertNotIn("203.0.113.7", click.visitor)
        self.assertEqual(hash_visitor("203.0.113.7"), click.visitor)

    def test_forwarded_for_uses_first_address(self):
        self.click("k3x9qa", ip="203.0.113.7, 10.0.0.1")
        self.assertEqual(
            hash_visitor("203.0.113.7"),
            ScoutOutreachClick.objects.get().visitor,
        )

    def test_unknown_code_is_not_recorded(self):
        self.assertEqual(404, self.click("zzzzzz").status_code)
        self.assertFalse(ScoutOutreachClick.objects.exists())

    def test_bad_target_is_not_recorded(self):
        self.assertEqual(404, self.click("k3x9qa", "../admin").status_code)

    def test_preview_crawlers_are_flagged(self):
        for ua in [
            "Discourse Forum Onebox v3.4.0",
            "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
            "Mozilla/5.0 (compatible; redditbot/1.0)",
            "python-requests/2.32",
            "",
        ]:
            with self.subTest(ua=ua):
                self.assertTrue(is_bot(ua))
        self.assertFalse(is_bot(BROWSER))


class OutreachStatsTestCase(ScoutLinksTestCase):
    def test_counts_unique_human_visitors_per_target(self):
        self.grant_scout()
        code = self.register().json()["code"]
        self.click(code, "discord", ip="203.0.113.7")
        self.click(code, "discord", ip="203.0.113.7")
        self.click(code, "discord", ip="198.51.100.2")
        self.click(code, "learning", ip="203.0.113.7")
        self.click(code, "discord", ua="Discourse Forum Onebox v3.4.0")

        response = self.client.get(f"{BASE_URL}/outreach", **self.auth)
        self.assertEqual(200, response.status_code)
        [row] = response.json()
        self.assertEqual({"discord": 2, "learning": 1}, row["clicks"])
        self.assertEqual(2, row["visitors"])
        self.assertIsNotNone(row["first_click_at"])

    def test_reply_without_clicks_is_listed(self):
        ScoutOutreach.objects.create(
            code="aaaaaa", surface="forums", thread_url=THREAD
        )
        [row] = outreach_stats(30)
        self.assertEqual(0, row["visitors"])
        self.assertEqual({}, row["clicks"])

    def test_stats_require_scout_feature(self):
        response = self.client.get(f"{BASE_URL}/outreach", **self.auth)
        self.assertEqual(403, response.status_code)
