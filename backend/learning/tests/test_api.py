"""Tests for Learning Center helpers and API endpoints."""

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone
from eveuniverse.models import EveFaction

from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EvePlayer,
)
from learning.helpers import (
    import_learning_progress,
    mark_learning_complete,
    recommend_persona,
    recompute_awards_for_user,
)
from learning.models import (
    Certificate,
    CertificateLearning,
    Learning,
    Persona,
    UserCertificateAward,
    UserLearningPreference,
    UserLearningProgress,
)

BASE = "/api/learning"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class LearningHelpersTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", password="x")
        self.l1 = Learning.objects.create(
            slug="intro",
            title="Intro",
            url="/learning/guides/intro/",
            content_kind="guide",
        )
        self.l2 = Learning.objects.create(
            slug="advanced",
            title="Advanced",
            url="/learning/guides/advanced/",
            content_kind="guide",
        )
        self.cert = Certificate.objects.create(
            slug="onboarding",
            title="Onboarding",
            personas=["alliance"],
            sort_order=1,
        )
        CertificateLearning.objects.create(
            certificate=self.cert, learning=self.l1, order=0
        )
        CertificateLearning.objects.create(
            certificate=self.cert, learning=self.l2, order=1
        )

    def test_partial_progress_does_not_award(self):
        mark_learning_complete(self.user, self.l1)
        self.assertEqual(UserCertificateAward.objects.count(), 0)

    def test_full_progress_awards_certificate(self):
        mark_learning_complete(self.user, self.l1)
        _, _, awarded = mark_learning_complete(self.user, self.l2)
        self.assertEqual(len(awarded), 1)
        self.assertEqual(awarded[0].certificate, self.cert)
        self.assertEqual(UserCertificateAward.objects.count(), 1)

    def test_complete_is_idempotent(self):
        mark_learning_complete(self.user, self.l1)
        mark_learning_complete(self.user, self.l2)
        _, created, awarded = mark_learning_complete(self.user, self.l2)
        self.assertFalse(created)
        self.assertEqual(awarded, [])
        self.assertEqual(UserLearningProgress.objects.count(), 2)
        self.assertEqual(UserCertificateAward.objects.count(), 1)

    def test_recompute_is_idempotent(self):
        mark_learning_complete(self.user, self.l1)
        mark_learning_complete(self.user, self.l2)
        again = recompute_awards_for_user(self.user)
        self.assertEqual(again, [])
        self.assertEqual(UserCertificateAward.objects.count(), 1)

    def test_import_merges_and_awards(self):
        result = import_learning_progress(
            user=self.user,
            completed_slugs=["intro", "advanced", "missing"],
            persona="alliance",
        )
        self.assertEqual(set(result["imported_slugs"]), {"intro", "advanced"})
        self.assertEqual(result["persona"], "alliance")
        self.assertEqual(UserCertificateAward.objects.count(), 1)
        pref = UserLearningPreference.objects.get(user=self.user)
        self.assertEqual(pref.persona, Persona.ALLIANCE)
        self.assertIsNotNone(pref.persona_confirmed_at)

    def test_import_does_not_overwrite_confirmed_persona(self):
        UserLearningPreference.objects.create(
            user=self.user,
            persona=Persona.MILITIA,
            persona_confirmed_at=timezone.now(),
        )

        result = import_learning_progress(
            user=self.user,
            completed_slugs=[],
            persona="alliance",
        )
        self.assertIsNone(result["persona"])
        pref = UserLearningPreference.objects.get(user=self.user)
        self.assertEqual(pref.persona, Persona.MILITIA)

    def test_unpublished_learning_not_required_for_award(self):
        unpublished = Learning.objects.create(
            slug="draft-extra",
            title="Draft Extra",
            url="/learning/guides/draft/",
            content_kind="guide",
            published=False,
        )
        CertificateLearning.objects.create(
            certificate=self.cert, learning=unpublished, order=2
        )
        mark_learning_complete(self.user, self.l1)
        _, _, awarded = mark_learning_complete(self.user, self.l2)
        self.assertEqual(len(awarded), 1)
        self.assertEqual(UserCertificateAward.objects.count(), 1)

    def test_unpublished_certificate_not_awarded(self):
        self.cert.published = False
        self.cert.save(update_fields=["published"])
        mark_learning_complete(self.user, self.l1)
        mark_learning_complete(self.user, self.l2)
        self.assertEqual(UserCertificateAward.objects.count(), 0)
        self.assertEqual(recompute_awards_for_user(self.user), [])


class PersonaRecommendationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pilot", password="x")

    def _set_primary(self, character: EveCharacter):
        EvePlayer.objects.update_or_create(
            user=self.user,
            defaults={
                "primary_character": character,
                "nickname": character.character_name,
            },
        )

    def test_no_primary_recommends_other(self):
        result = recommend_persona(self.user)
        self.assertEqual(result["persona"], Persona.OTHER)
        self.assertIsNone(result["corp_type"])

    def test_alliance_corp_recommends_alliance(self):
        alliance = EveAlliance.objects.create(
            alliance_id=99011978, name="Minmatar Fleet"
        )
        corp = EveCorporation.objects.create(
            corporation_id=987001,
            alliance=alliance,
        )
        character = EveCharacter.objects.create(
            character_id=900000111,
            character_name="Ally",
            corporation_id=corp.corporation_id,
        )
        self._set_primary(character)
        result = recommend_persona(self.user)
        self.assertEqual(result["persona"], Persona.ALLIANCE)
        self.assertEqual(result["corp_type"], "alliance")

    def test_militia_corp_recommends_militia(self):
        faction = EveFaction.objects.create(
            id=500002,
            name="Minmatar Republic",
            description="Minmatar",
            is_unique=True,
            size_factor=1.0,
            station_count=1,
            station_system_count=1,
        )
        corp = EveCorporation.objects.create(
            corporation_id=987002,
            faction=faction,
        )
        character = EveCharacter.objects.create(
            character_id=900000222,
            character_name="MilitiaPilot",
            corporation_id=corp.corporation_id,
        )
        self._set_primary(character)
        result = recommend_persona(self.user)
        self.assertEqual(result["persona"], Persona.MILITIA)
        self.assertEqual(result["corp_type"], "militia")


class LearningApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="apiuser", password="x")
        self.token = _make_token(self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

        self.l1 = Learning.objects.create(
            slug="fw-basics",
            title="FW Basics",
            url="/learning/guides/faction-warfare-basics/",
            content_kind="guide",
        )
        self.l2 = Learning.objects.create(
            slug="fw-plexing",
            title="FW Plexing",
            url="/learning/guides/faction-warfare-plexing/",
            content_kind="guide",
        )
        self.cert = Certificate.objects.create(
            slug="faction-warfare",
            title="Faction Warfare",
            personas=["alliance", "militia"],
            sort_order=2,
        )
        CertificateLearning.objects.create(
            certificate=self.cert, learning=self.l1, order=0
        )
        CertificateLearning.objects.create(
            certificate=self.cert, learning=self.l2, order=1
        )
        Certificate.objects.create(
            slug="onboarding",
            title="Alliance Onboarding",
            personas=["alliance"],
            sort_order=1,
        )

    def test_list_certificates_public(self):
        r = self.client.get(f"{BASE}/certificates")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 2)

    def test_list_certificates_filtered_by_persona(self):
        r = self.client.get(f"{BASE}/certificates?persona=militia")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["slug"], "faction-warfare")
        self.assertEqual(data[0]["learning_count"], 2)

    def test_get_certificate(self):
        r = self.client.get(f"{BASE}/certificates/faction-warfare")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["slug"], "faction-warfare")
        self.assertEqual(
            [item["slug"] for item in data["learnings"]],
            ["fw-basics", "fw-plexing"],
        )

    def test_get_certificate_404(self):
        r = self.client.get(f"{BASE}/certificates/missing")
        self.assertEqual(r.status_code, 404)

    def test_me_requires_auth(self):
        r = self.client.get(f"{BASE}/me")
        self.assertEqual(r.status_code, 401)

    def test_me_empty(self):
        r = self.client.get(f"{BASE}/me", **self.auth)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsNone(data["persona"])
        self.assertEqual(data["completed_learning_slugs"], [])
        self.assertEqual(data["awards"], [])

    def test_put_persona(self):
        r = self.client.put(
            f"{BASE}/persona",
            data={"persona": "militia"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["persona"], "militia")
        self.assertTrue(r.json()["confirmed"])

    def test_put_persona_invalid(self):
        r = self.client.put(
            f"{BASE}/persona",
            data={"persona": "pirate"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(r.status_code, 400)

    def test_complete_learning_and_award(self):
        r1 = self.client.post(
            f"{BASE}/learnings/fw-basics/complete",
            **self.auth,
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["newly_awarded"], [])

        r2 = self.client.post(
            f"{BASE}/learnings/fw-plexing/complete",
            **self.auth,
        )
        self.assertEqual(r2.status_code, 200)
        awards = r2.json()["newly_awarded"]
        self.assertEqual(len(awards), 1)
        self.assertEqual(awards[0]["slug"], "faction-warfare")

        me = self.client.get(f"{BASE}/me", **self.auth).json()
        self.assertEqual(
            set(me["completed_learning_slugs"]),
            {"fw-basics", "fw-plexing"},
        )
        self.assertEqual(len(me["awards"]), 1)

    def test_import_endpoint(self):
        r = self.client.post(
            f"{BASE}/import",
            data={
                "completed_learning_slugs": ["fw-basics", "fw-plexing"],
                "persona": "alliance",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(
            set(data["imported_slugs"]), {"fw-basics", "fw-plexing"}
        )
        self.assertEqual(data["persona"], "alliance")
        self.assertEqual(len(data["awards"]), 1)

    def test_persona_recommendation_endpoint(self):
        r = self.client.get(f"{BASE}/persona/recommendation", **self.auth)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["persona"], "other")

    def test_list_excludes_unpublished_certificates(self):
        Certificate.objects.filter(slug="onboarding").update(published=False)
        r = self.client.get(f"{BASE}/certificates")
        self.assertEqual(r.status_code, 200)
        slugs = {item["slug"] for item in r.json()}
        self.assertIn("faction-warfare", slugs)
        self.assertNotIn("onboarding", slugs)

    def test_get_unpublished_certificate_404(self):
        Certificate.objects.filter(slug="faction-warfare").update(
            published=False
        )
        r = self.client.get(f"{BASE}/certificates/faction-warfare")
        self.assertEqual(r.status_code, 404)

    def test_get_certificate_omits_unpublished_learnings(self):
        Learning.objects.filter(slug="fw-plexing").update(published=False)
        r = self.client.get(f"{BASE}/certificates/faction-warfare")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(
            [item["slug"] for item in data["learnings"]], ["fw-basics"]
        )
        self.assertEqual(data["learning_count"], 1)
