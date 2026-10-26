"""The Training tab: goals, plans, suggestions and account moves."""

from django.contrib.auth.models import User
from django.test import Client

from app.test import TestCase
from capabilities import services, training
from capabilities.models import (
    CapabilitySkill,
    CharacterAccount,
    CharacterAccountLink,
    CharacterAccountMember,
    CharacterShipGoal,
)
from capabilities.engine.plan import step_days
from capabilities.tests.helpers import (
    all_skills_at,
    fixture_eft,
    fixture_sde,
    store_fixture_snapshot,
)
from capabilities.tests.test_services import give_skills
from applications.l3arn import L3ARN_CORPORATION_NAME
from eveonline.models import EveCharacter, EveCorporation, EvePlayer
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting

SDE = fixture_sde()
GUARDIAN = 11987
NAPOC = 17726


class TrainingTestCase(TestCase):
    def setUp(self):
        super().setUp()
        store_fixture_snapshot()
        self.doctrine = EveDoctrine.objects.create(
            name="Armor", type="strategic", description=""
        )
        self.guardian = self._fit("guardian", GUARDIAN)
        self.logi = self._character(3001, "Logi", all_skills_at(SDE, 5))
        hard_only = all_skills_at(SDE, 5)
        hard_only[SDE.resolve("Capacitor Management")] = 0
        self.alt = self._character(3002, "Alt", hard_only)
        self._rate()

    def _fit(self, name, ship_id, doctrine=None):
        eft = fixture_eft(name)
        fitting = EveFitting.objects.create(
            name=EveFitting.fitting_name_from_eft(eft),
            ship_id=ship_id,
            description="",
            eft_format=eft,
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine or self.doctrine, fitting=fitting, role="primary"
        )
        return fitting

    def _character(self, character_id, name, skills, user=None):
        character = EveCharacter.objects.create(
            character_id=character_id,
            character_name=name,
            user=user or self.user,
        )
        give_skills(character, skills)
        return character

    def _rate(self):
        services.recompute_all_requirements()
        services.refresh_readiness()
        services.refresh_capabilities()

    def _summary(self, view, name):
        for account in view["accounts"]:
            for character in account["characters"]:
                if character["name"] == name:
                    return character
        for character in view["unplaced"]:
            if character["name"] == name:
                return character
        raise AssertionError(name)


class SkillInfoTest(TrainingTestCase):
    def test_each_snapshot_fills_skill_ranks_and_prerequisites(self):
        skill = CapabilitySkill.objects.get(
            skill_id=SDE.resolve("Logistics Cruisers")
        )
        self.assertGreater(skill.rank, 1)
        self.assertTrue(skill.prerequisites)
        self.assertEqual(services.refresh_skill_info(), 0)


class OverviewTest(TrainingTestCase):
    def test_one_ship_trains_and_the_rest_wait(self):
        napoc = self._fit("napoc", NAPOC)
        self._rate()
        training.add_goal(self.user, self.alt.character_id, self.guardian.pk)
        training.add_goal(self.user, self.alt.character_id, napoc.pk)
        alt = self._summary(training.overview(self.user), "Alt")
        self.assertEqual(alt["training"]["name"], "Guardian")
        self.assertGreater(alt["training"]["days"], 0)
        self.assertGreaterEqual(alt["training"]["skills"], 1)
        self.assertEqual(len(alt["goals"]), 2)

        training.update_goal(
            self.user, self.alt.character_id, napoc.pk, first=True
        )
        alt = self._summary(training.overview(self.user), "Alt")
        self.assertEqual(alt["training"]["fitting_id"], napoc.pk)
        self.assertEqual(alt["queued"], ["Guardian"])

    def test_ready_ships_and_what_you_can_bring(self):
        view = training.overview(self.user)
        logi = self._summary(view, "Logi")
        self.assertEqual(
            [s["fitting_id"] for s in logi["ready"]], [self.guardian.pk]
        )
        bring = view["bring"]
        self.assertFalse(bring["academy"])
        self.assertEqual(bring["columns"], ["Logistics"])
        [armor] = bring["doctrines"]
        self.assertEqual(armor["name"], "Armor")
        self.assertTrue(armor["strategic"])
        self.assertEqual(
            armor["cells"],
            [
                {
                    "column": "Logistics",
                    "ships": 1,
                    "ready": 1,
                    "state": "ready",
                    "seats": 1,
                    "days": None,
                }
            ],
        )
        # Logi and Alt are on no account, so each is a seat of its own.
        self.assertEqual(bring["seats"], 2)
        self.assertEqual(armor["seats"], 1)

    def test_one_account_is_one_seat(self):
        account = CharacterAccount.objects.create(user=self.user, number=1)
        for character in (self.logi, self.alt):
            CharacterAccountMember.objects.create(
                account=account, character=character
            )
        bring = training.overview(self.user)["bring"]
        self.assertEqual(bring["seats"], 1)
        self.assertEqual(bring["doctrines"][0]["cells"][0]["seats"], 1)

    def test_a_role_nobody_flies_says_how_soon(self):
        training.set_not_for_fleets(self.user, self.logi.character_id, True)
        [cell] = training.overview(self.user)["bring"]["doctrines"][0]["cells"]
        self.assertEqual(cell["seats"], 0)
        self.assertGreater(cell["days"], 0)

    def test_a_character_without_goals_gets_the_nearest_fits(self):
        alt = self._summary(training.overview(self.user), "Alt")
        self.assertEqual(
            [s["fitting_id"] for s in alt["suggestions"]], [self.guardian.pk]
        )
        self.assertFalse(alt["nothing_close"])

    def test_not_for_fleets_has_no_suggestions_and_does_not_count(self):
        training.set_not_for_fleets(self.user, self.logi.character_id, True)
        training.set_not_for_fleets(self.user, self.alt.character_id, True)
        view = training.overview(self.user)
        self.assertEqual(self._summary(view, "Alt")["suggestions"], [])
        [cell] = view["bring"]["doctrines"][0]["cells"]
        self.assertEqual(cell["state"], "needs_work")

    def test_a_ready_goal_is_done_until_optimal_is_asked_for(self):
        training.add_goal(self.user, self.logi.character_id, self.guardian.pk)
        logi = self._summary(training.overview(self.user), "Logi")
        self.assertTrue(logi["all_done"])
        self.assertIsNone(logi["training"])


class BringTest(TrainingTestCase):
    def _secondary(self):
        napoc = self._fit("napoc", NAPOC)
        EveDoctrineFitting.objects.filter(fitting=napoc).update(
            role="secondary"
        )
        self._rate()
        return napoc

    def _make_academy(self):
        EveCorporation.objects.create(
            corporation_id=98000001, name=L3ARN_CORPORATION_NAME
        )
        self.logi.corporation_id = 98000001
        self.logi.save()
        EvePlayer.objects.create(user=self.user, primary_character=self.logi)

    def test_secondary_fits_are_hidden_outside_the_academy(self):
        napoc = self._secondary()
        view = training.overview(self.user)
        self.assertEqual(view["bring"]["columns"], ["Logistics"])
        options = training.ship_options(self.user, self.alt.character_id)
        self.assertNotIn(napoc.pk, [o["fitting_id"] for o in options])

    def test_academy_pilots_see_only_secondary_fits(self):
        napoc = self._secondary()
        self._make_academy()
        view = training.overview(self.user)
        self.assertTrue(view["bring"]["academy"])
        self.assertEqual(view["bring"]["columns"], ["DPS"])
        options = training.ship_options(self.user, self.alt.character_id)
        self.assertEqual([o["fitting_id"] for o in options], [napoc.pk])

    def test_a_cell_lists_its_ships_and_the_closest_character(self):
        cell = training.doctrine_cell(self.user, self.doctrine.pk, "Logistics")
        [ship] = cell["ships"]
        self.assertEqual(ship["fitting_id"], self.guardian.pk)
        self.assertEqual(ship["accounts"], 1)
        self.assertIsNone(ship["closest"])
        ready, closest = cell["seats"]
        self.assertEqual((ready["name"], ready["ready"]), ("Logi", True))
        self.assertEqual(ready["ships"], ["Guardian"])
        self.assertEqual((closest["name"], closest["ready"]), ("Alt", False))
        self.assertEqual(closest["fitting_id"], self.guardian.pk)
        self.assertGreater(closest["days"], 0)

        training.set_not_for_fleets(self.user, self.logi.character_id, True)
        cell = training.doctrine_cell(self.user, self.doctrine.pk, "Logistics")
        self.assertEqual(cell["ships"][0]["closest"]["name"], "Alt")
        with self.assertRaises(training.TrainingError):
            training.doctrine_cell(self.user, self.doctrine.pk, "DPS")


class PlanTest(TrainingTestCase):
    def test_plan_lists_the_missing_levels_in_order(self):
        view = training.plan_view(
            self.user, self.alt.character_id, self.guardian.pk
        )
        names = [step["name"] for step in view["ready_steps"]]
        self.assertIn("Capacitor Management", names)
        levels = [
            step["level"]
            for step in view["ready_steps"]
            if step["name"] == "Capacitor Management"
        ]
        self.assertEqual(levels, sorted(levels))
        self.assertTrue(view["eve_text"].startswith(names[0]))
        self.assertEqual(view["queue_skills"], len(view["ready_steps"]))
        self.assertEqual(view["flown_by"], ["Logi"])
        status = training.overview(self.user)
        self.assertEqual(
            self._summary(status, "Alt")["suggestions"][0]["days"],
            view["ready_days"],
        )

    def test_days_use_the_skill_rank_before_the_nightly_fills_it(self):
        CapabilitySkill.objects.all().delete()
        view = training.plan_view(
            self.user, self.alt.character_id, self.guardian.pk
        )
        step = max(
            (
                s
                for s in view["ready_steps"]
                if s["name"] == "Capacitor Management"
            ),
            key=lambda s: s["level"],
        )
        rank = SDE.skill_rank(SDE.resolve("Capacitor Management"))
        self.assertGreater(rank, 1)
        self.assertAlmostEqual(
            step["days"], round(step_days(rank, step["level"]), 2), places=2
        )

    def test_optimal_adds_its_steps_to_the_queue(self):
        training.add_goal(self.user, self.alt.character_id, self.guardian.pk)
        training.update_goal(
            self.user,
            self.alt.character_id,
            self.guardian.pk,
            target=CharacterShipGoal.TARGET_OPTIMAL,
        )
        view = training.plan_view(
            self.user, self.alt.character_id, self.guardian.pk
        )
        self.assertEqual(view["target"], "optimal")
        self.assertEqual(
            view["queue_skills"],
            len(view["ready_steps"]) + len(view["optimal_steps"]),
        )

    def test_only_doctrine_fits_and_own_characters(self):
        other = EveFitting.objects.create(
            name="Loose fit", ship_id=GUARDIAN, description="", eft_format=""
        )
        with self.assertRaises(training.TrainingError):
            training.add_goal(self.user, self.alt.character_id, other.pk)
        stranger = User.objects.create(username="stranger")
        with self.assertRaises(training.TrainingError):
            training.add_goal(
                stranger, self.alt.character_id, self.guardian.pk
            )

    def test_ship_options_mark_added_fits(self):
        training.add_goal(self.user, self.alt.character_id, self.guardian.pk)
        options = training.ship_options(self.user, self.alt.character_id)
        self.assertEqual(options[0]["fitting_id"], self.guardian.pk)
        self.assertTrue(options[0]["added"])
        self.assertEqual(options[0]["doctrines"], ["Armor"])


class AccountMoveTest(TrainingTestCase):
    def _link(self, a, b, fleets=3):
        CharacterAccountLink.objects.create(
            user=self.user,
            character_a=a,
            character_b=b,
            fleets_together=fleets,
        )

    def test_pilot_placements_survive_inference(self):
        third = self._character(3003, "Third", {})
        self._link(self.logi, self.alt)
        self._link(self.logi, third)
        services.infer_accounts()
        self.assertEqual(
            CharacterAccount.objects.filter(user=self.user).count(), 2
        )
        training.move_character(
            self.user, self.alt.character_id, None, new_account=True
        )
        moved = CharacterAccountMember.objects.get(character=self.alt)
        self.assertEqual(moved.source, CharacterAccount.SOURCE_PILOT)
        number = moved.account.number

        services.infer_accounts()
        moved.refresh_from_db()
        self.assertEqual(moved.account.number, number)
        # The others are placed again around it.
        self.assertTrue(
            CharacterAccountMember.objects.filter(character=third).exists()
        )

    def test_not_on_an_account(self):
        self._link(self.logi, self.alt)
        services.infer_accounts()
        training.move_character(self.user, self.alt.character_id, None)
        services.infer_accounts()
        view = training.overview(self.user)
        self.assertEqual([c["name"] for c in view["unplaced"]], ["Alt"])

    def test_a_full_account_refuses_a_fourth_character(self):
        others = [
            self._character(3010 + i, f"Member {i}", {}) for i in range(3)
        ]
        account = CharacterAccount.objects.create(
            user=self.user, number=1, source=CharacterAccount.SOURCE_PILOT
        )
        for character in others:
            CharacterAccountMember.objects.create(
                character=character,
                account=account,
                source=CharacterAccount.SOURCE_PILOT,
            )
        with self.assertRaises(training.TrainingError):
            training.move_character(self.user, self.alt.character_id, 1)
        options = training.account_options(self.user, self.alt.character_id)
        self.assertTrue(options["accounts"][0]["full"])


class TrainingApiTest(TrainingTestCase):
    def _client(self):
        return Client(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_overview_and_goal_round_trip(self):
        client = self._client()
        response = client.post(
            f"/api/training/characters/{self.alt.character_id}/goals",
            {"fitting_id": self.guardian.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        response = client.get("/api/training/")
        self.assertEqual(response.status_code, 200, response.content)
        alt = self._summary(response.json(), "Alt")
        self.assertEqual(alt["training"]["fitting_id"], self.guardian.pk)
        response = client.get(
            f"/api/training/characters/{self.alt.character_id}"
            f"/plans/{self.guardian.pk}"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["is_training"])

    def test_doctrine_cell(self):
        response = self._client().get(
            f"/api/training/doctrines/{self.doctrine.pk}/Logistics"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["name"], "Armor")
        response = self._client().get(
            f"/api/training/doctrines/{self.doctrine.pk}/Recon"
        )
        self.assertEqual(response.status_code, 404)

    def test_someone_elses_character_is_not_found(self):
        stranger = User.objects.create(username="stranger")
        other = self._character(3999, "Other", {}, user=stranger)
        response = self._client().get(
            f"/api/training/characters/{other.character_id}"
        )
        self.assertEqual(response.status_code, 404)

    def test_needs_a_login(self):
        self.assertEqual(Client().get("/api/training/").status_code, 401)
