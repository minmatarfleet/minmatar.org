"""Author-facing learning endpoints: access, writes and audit entries."""

from django.contrib.auth.models import Permission, User

from app.test import TestCase
from app.testing import auth_headers
from audit.models import AuditEntry
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncPilotFeaturesCommand,
)
from groups.models import PilotFeature
from learning.models import Certificate, Learning, UserCertificateAward
from onboarding.models import OnboardingProgram
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

BASE = "/api/learning/manage"


class LearningManageTestCase(TestCase):
    def setUp(self):
        super().setUp()
        clear_feature_cache()
        tribe = Tribe.objects.create(
            name="Pulse", slug="pulse", chief=self.user
        )
        self.group = TribeGroup.objects.create(
            tribe=tribe, name="Thinkspeak", code="pulse.thinkspeak"
        )
        SyncPilotFeaturesCommand().handle()
        for code in ("learning.manage", "skillsets.manage"):
            PilotFeature.objects.get(code=code).tribe_groups.set([self.group])
        clear_feature_cache()
        self.outsider = User.objects.create(username="outsider")

    def _join(self):
        TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        clear_feature_cache()

    def _post(self, path, body, user=None):
        return self.client.post(
            f"{BASE}/{path}",
            body,
            content_type="application/json",
            **auth_headers(user or self.user),
        )

    def _put(self, path, body):
        return self.client.put(
            f"{BASE}/{path}",
            body,
            content_type="application/json",
            **auth_headers(self.user),
        )

    def test_non_members_are_refused(self):
        for path in ("guides", "certificates", "onboarding", "skillsets"):
            response = self.client.get(
                f"{BASE}/{path}", **auth_headers(self.outsider)
            )
            self.assertEqual(response.status_code, 403, path)
        response = self._post(
            "guides",
            {"slug": "a", "title": "A", "url": "/a"},
            user=self.outsider,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Learning.objects.filter(slug="a").exists())

    def test_legacy_permission_backs_the_api(self):

        self.outsider.user_permissions.add(
            Permission.objects.get(codename="change_certificate")
        )
        response = self.client.get(
            f"{BASE}/certificates", **auth_headers(self.outsider)
        )
        self.assertEqual(response.status_code, 200)

    def test_guide_create_edit_and_audit(self):
        self._join()
        response = self._post(
            "guides",
            {"slug": "intro", "title": "Intro", "url": "/learning/intro"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        response = self._put(
            "guides/intro",
            {
                "slug": "intro",
                "title": "Intro 2",
                "url": "/learning/intro",
                "published": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        guide = Learning.objects.get(slug="intro")
        self.assertEqual(guide.title, "Intro 2")
        self.assertFalse(guide.published)
        self.assertEqual(AuditEntry.objects.filter(user=self.user).count(), 2)

    def test_guide_validation(self):
        self._join()
        bad = self._post(
            "guides", {"slug": "Bad Slug", "title": "x", "url": "/x"}
        )
        self.assertEqual(bad.status_code, 400)
        self._post("guides", {"slug": "a", "title": "A", "url": "/a"})
        dup = self._post("guides", {"slug": "a", "title": "A", "url": "/a"})
        self.assertEqual(dup.status_code, 400)

    def test_certificate_orders_guides(self):
        self._join()
        for slug in ("one", "two"):
            Learning.objects.create(slug=slug, title=slug, url="/x")
        response = self._post(
            "certificates",
            {
                "slug": "basics",
                "title": "Basics",
                "personas": ["alliance"],
                "learning_slugs": ["two", "one"],
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["learning_slugs"], ["two", "one"])
        response = self._put(
            "certificates/basics",
            {
                "slug": "basics",
                "title": "Basics",
                "learning_slugs": ["one"],
                "published": False,
            },
        )
        self.assertEqual(response.json()["learning_slugs"], ["one"])
        self.assertFalse(Certificate.objects.get(slug="basics").published)

    def test_certificate_rejects_unknown_guide_and_persona(self):
        self._join()
        response = self._post(
            "certificates",
            {"slug": "c", "title": "C", "learning_slugs": ["nope"]},
        )
        self.assertEqual(response.status_code, 400)
        response = self._post(
            "certificates", {"slug": "c", "title": "C", "personas": ["x"]}
        )
        self.assertEqual(response.status_code, 400)

    def test_award_and_revoke_need_a_reason_and_are_audited(self):
        self._join()
        Certificate.objects.create(slug="basics", title="Basics")
        body = {
            "username": "outsider",
            "certificate_slug": "basics",
            "reason": "",
        }
        self.assertEqual(self._post("awards", body).status_code, 400)
        body["reason"] = "Completed in person"
        self.assertEqual(self._post("awards", body).status_code, 200)
        self.assertTrue(
            UserCertificateAward.objects.filter(user=self.outsider).exists()
        )
        self.assertEqual(self._post("awards/revoke", body).status_code, 200)
        self.assertFalse(UserCertificateAward.objects.exists())
        summaries = list(
            AuditEntry.objects.order_by("id").values_list("summary", flat=True)
        )
        self.assertEqual(len(summaries), 2)
        self.assertIn("Completed in person", summaries[0])

    def test_bump_changes_the_version(self):
        self._join()
        before = OnboardingProgram.objects.get_or_create(program_type="srp")[
            0
        ].version
        response = self._post("onboarding/srp/version", None)
        self.assertEqual(response.status_code, 200)
        after = OnboardingProgram.objects.get(program_type="srp").version
        self.assertNotEqual(before, after)
        self.assertEqual(
            self._post("onboarding/nope/version", None).status_code, 404
        )

    def test_skillset_validation_and_search(self):
        self._join()
        response = self._post(
            "skillsets",
            {"name": "Set", "skills": [{"name": "Nonexistent", "level": 5}]},
        )
        self.assertEqual(response.status_code, 400)
        response = self._post(
            "skillsets",
            {"name": "Set", "skills": [{"name": "Gunnery", "level": 9}]},
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.get(
            f"{BASE}/skillsets/skill-search?q=gu", **auth_headers(self.user)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
