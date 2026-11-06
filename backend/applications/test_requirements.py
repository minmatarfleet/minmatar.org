from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import signals
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from applications.models import (
    CorporationRequirement as Rule,
    EveCorporationApplication,
)
from applications.requirements import rules as R
from applications.requirements.evaluate import (
    MET,
    TRAINING,
    UNKNOWN,
    UNMET,
    evaluate,
    format_days,
)
from applications.requirements.services import (
    interview_topics,
    member_pass_rates,
    save_interview_topics,
)
from capabilities.models import (
    CharacterAccount,
    CharacterAccountMember,
    CharacterFittingReadiness,
    FittingRequirementSet,
)
from eveonline.models import EveCharacter, EveCorporation, EvePlayer
from eveonline.models.characters import (
    EveCharacterCorporationHistory,
    EveCharacterKillmail,
    EveCharacterSkill,
)
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting

BASE_URL = "/api/applications/"
VAGABOND = 11999
NAGLFAR = 19722


class RequirementsTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        signals.post_save.disconnect(
            sender=EveCorporation,
            dispatch_uid="eve_corporation_post_save",
        )
        super().setUp()
        cache.clear()
        self.client = Client()
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134,
            name="Rattini Tribe",
            requirements="- Sense of humor\n- At least one rat meme",
        )
        self.ceo_user = User.objects.create(username="ceo")
        self.ceo = EveCharacter.objects.create(
            character_id=1001, character_name="Ceo", user=self.ceo_user
        )
        self.corporation.ceo = self.ceo
        self.corporation.save()
        self.main = self._character(2001, "Main")
        EvePlayer.objects.update_or_create(
            user=self.user, defaults={"primary_character": self.main}
        )
        self.alt = self._character(2002, "Alt")
        self.doctrine = EveDoctrine.objects.create(
            name="Cruisers", type="strategic", description=""
        )

    # helpers

    def _character(self, character_id, name, user=None):
        return EveCharacter.objects.create(
            character_id=character_id,
            character_name=name,
            user=user or self.user,
        )

    def _fitting(self, ship_id, capability="DPS", doctrine=None):
        fitting = EveFitting.objects.create(
            name=f"Fit {ship_id} {capability}",
            ship_id=ship_id,
            description="",
            eft_format="",
        )
        if doctrine:
            EveDoctrineFitting.objects.create(
                doctrine=doctrine, fitting=fitting, role="primary"
            )
        requirement_set = FittingRequirementSet.objects.create(
            fitting=fitting,
            sde_build=1,
            rules_version=1,
            input_key="x",
            capability=capability,
        )
        return fitting, requirement_set

    def _ready(self, character, fitting_and_set, hard=True, days=0.0):
        fitting, requirement_set = fitting_and_set
        CharacterFittingReadiness.objects.create(
            character=character,
            fitting=fitting,
            requirement_set=requirement_set,
            hard_ready=hard,
            doctrine_ready=hard,
            days_to_hard=days,
            days_to_core=days,
        )

    def _rule(self, kind, params, who=Rule.WHO_ANY, importance="required"):
        return Rule.objects.create(
            corporation=self.corporation,
            kind=kind,
            params=params,
            who=who,
            importance=importance,
        )

    def _status(self, rule, user=None):
        user_id = (user or self.user).id
        return evaluate([rule], [user_id])[user_id][0]

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}


class RuleTextTest(RequirementsTestCase):
    def test_sentences(self):
        dread = Rule(
            kind=Rule.KIND_SHIPS,
            params={"target": "capability", "capability": "Dreads"},
            who=Rule.WHO_OTHER_ACCOUNT,
        )
        self.assertEqual(
            R.describe(dread),
            "An alt on another account that can fly a Dreadnought",
        )
        cruisers = Rule(
            kind=Rule.KIND_SHIPS,
            params={"target": "doctrine", "doctrine_id": self.doctrine.pk},
            who=Rule.WHO_ANY,
        )
        self.assertEqual(
            R.describe(cruisers, {self.doctrine.pk: "Cruisers"}),
            "Fly our Cruisers doctrine",
        )
        kills = Rule(
            kind=Rule.KIND_KILLS, params={"months": 6, "active_months": 4}
        )
        self.assertEqual(R.describe(kills), "Kills in 4 of the last 6 months")
        sp = Rule(
            kind=Rule.KIND_SKILL_POINTS,
            params={"minimum": 20_000_000},
            who=Rule.WHO_MAIN,
        )
        self.assertEqual(R.describe(sp), "20M+ skill points on your main")
        tz = Rule(
            kind=Rule.KIND_PRIME_TIME, params={"brackets": ["EUTZ", "USTZ"]}
        )
        self.assertEqual(R.describe(tz), "Plays in EUTZ or USTZ")

    def test_clean_rejects_bad_params(self):
        with self.assertRaises(R.RuleError):
            R.clean_rule(
                "ships",
                {"target": "capability", "capability": "Boats"},
                "any",
                "required",
            )
        with self.assertRaises(R.RuleError):
            R.clean_rule(
                "kills", {"months": 6, "active_months": 9}, "any", "required"
            )
        with self.assertRaises(R.RuleError):
            R.clean_rule(
                "kills",
                {"months": 6, "active_months": 4},
                "other_account",
                "required",
            )
        clean = R.clean_rule(
            "prime_time",
            {"brackets": ["USTZ", "EUTZ", "nope"]},
            "main",
            "preferred",
        )
        self.assertEqual(clean.params, {"brackets": ["USTZ", "EUTZ"]})
        self.assertEqual(clean.who, "any")

    def test_format_days(self):
        self.assertEqual(format_days(4.25), "4d 6h")
        self.assertEqual(format_days(0.01), "1h")
        self.assertEqual(format_days(2), "2d")


class EvaluateTest(RequirementsTestCase):
    def test_doctrine_ready_training_and_unknown(self):
        rule = self._rule(
            "ships", {"target": "doctrine", "doctrine_id": self.doctrine.pk}
        )
        self.assertEqual(self._status(rule).status, UNKNOWN)

        fit = self._fitting(VAGABOND, doctrine=self.doctrine)
        self._ready(self.alt, fit, hard=False, days=4.25)
        check = self._status(rule)
        self.assertEqual(check.status, TRAINING)
        self.assertTrue(check.detail.endswith("in 4d 6h"))
        self.assertTrue(check.blocks)

        self._ready(self.main, fit, hard=True)
        check = self._status(rule)
        self.assertEqual(check.status, MET)
        self.assertEqual(check.ship_type_ids, [VAGABOND])

    def test_main_only_ignores_alts(self):
        fit = self._fitting(VAGABOND, doctrine=self.doctrine)
        self._ready(self.alt, fit, hard=True)
        self._ready(self.main, fit, hard=False, days=1)
        rule = self._rule(
            "ships",
            {"target": "doctrine", "doctrine_id": self.doctrine.pk},
            who=Rule.WHO_MAIN,
        )
        self.assertEqual(self._status(rule).status, TRAINING)

    def test_other_account_skips_characters_on_the_mains_account(self):
        dread = self._fitting(NAGLFAR, capability="Dreads")
        self._ready(self.alt, dread, hard=True)
        rule = self._rule(
            "ships",
            {"target": "capability", "capability": "Dreads"},
            who=Rule.WHO_OTHER_ACCOUNT,
        )
        self.assertEqual(self._status(rule).status, MET)

        account = CharacterAccount.objects.create(user=self.user, number=1)
        CharacterAccountMember.objects.create(
            character=self.main, account=account
        )
        CharacterAccountMember.objects.create(
            character=self.alt, account=account
        )
        self.assertEqual(self._status(rule).status, UNMET)

    def test_kills_count_months_and_skip_losses(self):
        rule = self._rule("kills", {"months": 6, "active_months": 2})
        now = timezone.now()
        for index, offset in enumerate([0, 0, 40]):
            EveCharacterKillmail.objects.create(
                id=index + 1,
                killmail_id=index + 1,
                killmail_hash="h",
                killmail_time=now - timedelta(days=offset),
                solar_system_id=1,
                ship_type_id=1,
                victim_character_id=9999,
                attackers="[]",
                items="[]",
                character=self.alt,
            )
        EveCharacterKillmail.objects.create(
            id=10,
            killmail_id=10,
            killmail_hash="h",
            killmail_time=now - timedelta(days=80),
            solar_system_id=1,
            ship_type_id=1,
            victim_character_id=self.alt.character_id,
            attackers="[]",
            items="[]",
            character=self.alt,
        )
        check = self._status(rule)
        self.assertEqual(check.status, MET)
        self.assertEqual(check.detail, "2 of 6 months")

    def test_skill_points_and_age(self):
        EveCharacterSkill.objects.create(
            skill_id=1,
            skill_name="A",
            skill_points=15_000_000,
            skill_level=5,
            character=self.alt,
        )
        sp = self._rule("skill_points", {"minimum": 20_000_000})
        self.assertEqual(self._status(sp).status, UNMET)
        EveCharacterSkill.objects.create(
            skill_id=2,
            skill_name="B",
            skill_points=6_000_000,
            skill_level=5,
            character=self.alt,
        )
        self.assertEqual(self._status(sp).status, MET)

        age = self._rule("character_age", {"months": 12}, who=Rule.WHO_MAIN)
        self.assertEqual(self._status(age).status, UNKNOWN)
        EveCharacterCorporationHistory.objects.create(
            character=self.main,
            record_id=1,
            corporation_id=1000167,
            start_date=timezone.now() - timedelta(days=400),
        )
        self.assertEqual(self._status(age).status, MET)

    def test_member_pass_rates(self):
        member = User.objects.create(username="member")
        member_main = self._character(3001, "Member", user=member)
        member_main.corporation_id = self.corporation.corporation_id
        member_main.save()
        EvePlayer.objects.update_or_create(
            user=member,
            defaults={"primary_character": member_main, "nickname": "member"},
        )
        fit = self._fitting(VAGABOND, doctrine=self.doctrine)
        self._ready(member_main, fit, hard=True)
        rule = self._rule(
            "ships", {"target": "doctrine", "doctrine_id": self.doctrine.pk}
        )
        sp = self._rule("skill_points", {"minimum": 20_000_000})
        scores = member_pass_rates(self.corporation, [rule, sp])
        self.assertEqual(scores["members"], 1)
        self.assertEqual(scores["rates"][rule.id], 100)
        self.assertIsNone(scores["rates"][sp.id])


class TopicsTest(RequirementsTestCase):
    def test_topics_round_trip_the_free_text_field(self):
        self.assertEqual(
            interview_topics(self.corporation),
            ["Sense of humor", "At least one rat meme"],
        )
        save_interview_topics(
            self.corporation, ["  Logi  ", "", "Logi", "Memes"]
        )
        self.corporation.refresh_from_db()
        self.assertEqual(self.corporation.requirements, "- Logi\n- Memes")


class EndpointsTest(RequirementsTestCase):
    def test_public_list_has_no_rules_and_topics_by_default(self):
        response = self.client.get(
            f"{BASE_URL}corporations/{self.corporation.corporation_id}/requirements"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["rules"], [])
        self.assertEqual(
            body["interview_topics"],
            ["Sense of humor", "At least one rat meme"],
        )

    def test_only_settings_editors_can_change_rules(self):
        url = f"{BASE_URL}corporations/{self.corporation.corporation_id}/requirements"
        payload = {
            "kind": "kills",
            "params": {"months": 6, "active_months": 4},
            "importance": "preferred",
        }
        response = self.client.post(
            url, payload, content_type="application/json", **self._auth()
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Rule.objects.count(), 0)

        self.corporation.ceo = self.main
        self.corporation.save()
        response = self.client.post(
            url, payload, content_type="application/json", **self._auth()
        )
        self.assertEqual(response.status_code, 200, response.content)
        rule_id = response.json()["id"]
        self.assertEqual(
            response.json()["text"], "Kills in 4 of the last 6 months"
        )

        response = self.client.patch(
            f"{url}/{rule_id}",
            {"importance": "required"},
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.json()["importance"], "required")

        response = self.client.post(
            url,
            {"kind": "kills", "params": {"months": 6, "active_months": 7}},
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.get(f"{url}/manage", **self._auth())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["rules"]), 1)

        response = self.client.put(
            f"{BASE_URL}corporations/{self.corporation.corporation_id}/interview-topics",
            {"topics": ["Memes"]},
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.json(), {"interview_topics": ["Memes"]})

        response = self.client.delete(f"{url}/{rule_id}", **self._auth())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Rule.objects.count(), 0)

    def test_required_rule_blocks_applying_and_unknown_does_not(self):
        rule = self._rule(
            "ships", {"target": "doctrine", "doctrine_id": self.doctrine.pk}
        )
        url = f"{BASE_URL}corporations/{self.corporation.corporation_id}"
        me = self.client.get(f"{url}/requirements/me", **self._auth()).json()
        self.assertTrue(me["can_apply"])
        self.assertEqual(me["checks"][0]["status"], "unknown")

        fit = self._fitting(VAGABOND, doctrine=self.doctrine)
        self._ready(self.main, fit, hard=False, days=2)
        me = self.client.get(f"{url}/requirements/me", **self._auth()).json()
        self.assertFalse(me["can_apply"])
        response = self.client.post(
            f"{url}/applications",
            {"description": "Hi"},
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Fly our Cruisers doctrine", response.json()["detail"])

        rule.importance = "preferred"
        rule.save()
        response = self.client.post(
            f"{url}/applications",
            {"description": "Hi"},
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        application_id = response.json()["application_id"]

        response = self.client.get(
            f"{url}/applications/{application_id}/requirements", **self._auth()
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["preferred_total"], 1)
        self.assertEqual(body["checks"][0]["status"], "training")
