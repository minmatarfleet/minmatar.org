from datetime import timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import Client
from django.utils import timezone

from eveuniverse.models import EveType, EveGroup, EveCategory

from app.test import TestCase

from eveonline.client import EsiResponse
from eveonline.models import EveCharacter
from eveonline.helpers.characters import set_primary_character
from combatlog.models import CombatLog
from fleets.models import EveFleet, EveFleetInstance
from fleets.tests import (
    disconnect_fleet_signals,
    setup_fleet_reference_data,
    make_test_fleet,
)
from srp.models import (
    EveFleetShipReimbursement,
    ShipReimbursementProgram,
    ShipReimbursementProgramAmount,
)
from srp.helpers import get_reimbursement_amount
from users.helpers import add_user_permission

BASE_URL = "/api/srp"

KM_CHAR = 634915984
KM_ID = 126008813
KM_HASH = "9c92aa157f138da9b5a64abbd8225893f1b8b5f0"
KM_LINK = f"https://esi.evetech.net/killmails/{KM_ID}/{KM_HASH}/"


class SrpRouterTestCase(TestCase):
    """Test cases for the market router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

        # Setup fleet stuff
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.fleet = make_test_fleet("Test fleet", self.user)

    @patch("srp.helpers.EsiClient")
    def test_basic_srp(self, esi_mock):
        esi = esi_mock.return_value

        fc_char = EveCharacter.objects.create(
            character_id=KM_CHAR,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        esi.get_character_killmail.return_value = EsiResponse(
            response_code=200,
            data={
                "victim": {
                    "character_id": fc_char.character_id,
                    "ship_type_id": 11400,
                },
                "killmail_time": "2025-04-02T11:47:15Z",
            },
        )
        esi.get_eve_type.return_value = EveType(
            id=11400,
            description="Jaguar",
            eve_group=EveGroup(),
        )

        data = {
            "external_killmail_link": KM_LINK,
            "fleet_id": self.fleet.id,
            "is_corp_ship": False,
            "category": "dps",
            "comments": "Testing FTW",
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual("dps", data["category"])
        self.assertEqual("Testing FTW", data["comments"])

    @patch("srp.helpers.EsiClient")
    def test_non_fleet_srp(self, esi_mock):
        esi = esi_mock.return_value

        self.make_superuser()

        fc_char = EveCharacter.objects.create(
            character_id=KM_CHAR,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        esi.get_character_killmail.return_value = EsiResponse(
            response_code=200,
            data={
                "victim": {
                    "character_id": fc_char.character_id,
                    "ship_type_id": 11400,
                },
                "killmail_time": "2025-04-02T11:47:15Z",
            },
        )
        esi.get_eve_type.return_value = EveType(
            id=11400,
            description="Jaguar",
            eve_group=EveGroup(),
        )

        # Create non-fleet SRP request
        data = {
            "external_killmail_link": KM_LINK,
            "is_corp_ship": False,
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        reimbursement = response.json()
        reimbursement_id = reimbursement["id"]
        self.assertIsNotNone(reimbursement_id)
        self.assertIsNone(reimbursement["fleet_id"])
        self.assertEqual("pending", reimbursement["status"])

        # Get all SRP requests
        response = self.client.get(
            f"{BASE_URL}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        reimbursements = response.json()
        self.assertEqual(1, len(reimbursements))
        self.assertEqual(reimbursement_id, reimbursements[0]["id"])

    def test_user_srp(self):
        self.make_superuser()
        fc_char = EveCharacter.objects.create(
            character_id=634915984,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        EveFleetShipReimbursement.objects.create(
            user=self.user,
            status="pending",
            killmail_id=1234,
            external_killmail_link="abc",
            character_id=fc_char.character_id,
            character_name=fc_char.character_name,
            primary_character_id=fc_char.character_id,
            primary_character_name=fc_char.character_name,
            amount=1.23,
            ship_name="Rifter",
            ship_type_id=1234567,
        )
        EveFleetShipReimbursement.objects.create(
            status="pending",
            killmail_id=2345,
            external_killmail_link="xyz",
            character_id=fc_char.character_id,
            character_name=fc_char.character_name,
            primary_character_id=fc_char.character_id,
            primary_character_name=fc_char.character_name,
            amount=1.23,
            ship_name="Rifter",
            ship_type_id=1234567,
        )

        response = self.client.get(
            f"{BASE_URL}?user_id={self.user.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        reimbursements = response.json()
        self.assertEqual(1, len(reimbursements))
        self.assertEqual("abc", reimbursements[0]["external_killmail_link"])

    def test_srp_values_from_database(self):
        category = EveCategory.objects.create(
            id=6,
            name="Ship",
            published=True,
        )
        destroyer_group = EveGroup.objects.create(
            id=4200,
            name="Destroyer",
            eve_category=category,
            published=True,
        )
        cruiser_group = EveGroup.objects.create(
            id=4201,
            name="Cruiser",
            eve_category=category,
            published=True,
        )
        thrasher_type = EveType.objects.create(
            id=16242,
            name="Thrasher",
            eve_group=destroyer_group,
            published=True,
        )
        stabber_type = EveType.objects.create(
            id=622,
            name="Stabber",
            eve_group=cruiser_group,
            published=True,
        )

        thrasher_program = ShipReimbursementProgram.objects.create(
            eve_type=thrasher_type
        )
        ShipReimbursementProgramAmount.objects.create(
            program=thrasher_program, srp_value=12000000
        )
        stabber_program = ShipReimbursementProgram.objects.create(
            eve_type=stabber_type
        )
        ShipReimbursementProgramAmount.objects.create(
            program=stabber_program, srp_value=20000000
        )
        self.assertEqual(12000000, get_reimbursement_amount(thrasher_type))
        self.assertEqual(20000000, get_reimbursement_amount(stabber_type))

    def test_srp_type_id_rule_takes_precedence(self):
        category = EveCategory.objects.create(
            id=7,
            name="Ship",
            published=True,
        )
        dread_group = EveGroup.objects.create(
            id=4300,
            name="Dreadnought",
            eve_category=category,
            published=True,
        )
        revelation_type = EveType.objects.create(
            id=19720,
            name="Revelation",
            eve_group=dread_group,
            published=True,
        )
        phoenix_type = EveType.objects.create(
            id=19726,
            name="Phoenix",
            eve_group=dread_group,
            published=True,
        )

        rev_program = ShipReimbursementProgram.objects.create(
            eve_type=revelation_type
        )
        ShipReimbursementProgramAmount.objects.create(
            program=rev_program, srp_value=3000000000
        )
        phoenix_program = ShipReimbursementProgram.objects.create(
            eve_type=phoenix_type
        )
        ShipReimbursementProgramAmount.objects.create(
            program=phoenix_program, srp_value=2200000000
        )
        self.assertEqual(3000000000, get_reimbursement_amount(revelation_type))

    def test_invalid_killmail_link(self):
        data = {
            "external_killmail_link": "This won't work",
            "is_corp_ship": False,
            "category": "dps",
            "comments": "Testing FTW",
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual("Killmail link not valid", response.json()["detail"])

    def test_get_srp_values(self):
        self.make_superuser()

        category = EveCategory.objects.create(
            id=8,
            name="Ship",
            published=True,
        )
        dread_group = EveGroup.objects.create(
            id=4400,
            name="Dreadnought",
            eve_category=category,
            published=True,
        )
        revelation_type = EveType.objects.create(
            id=19720,
            name="Revelation",
            eve_group=dread_group,
            published=True,
        )
        naglfar_type = EveType.objects.create(
            id=19724,
            name="Naglfar",
            eve_group=dread_group,
            published=True,
        )

        rev_program = ShipReimbursementProgram.objects.create(
            eve_type=revelation_type
        )
        ShipReimbursementProgramAmount.objects.create(
            program=rev_program, srp_value=3000000000
        )
        nag_program = ShipReimbursementProgram.objects.create(
            eve_type=naglfar_type
        )
        ShipReimbursementProgramAmount.objects.create(
            program=nag_program, srp_value=2200000000
        )

        response = self.client.get(
            f"{BASE_URL}/programs",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        rows = response.json()
        self.assertEqual(2, len(rows))
        type_names = {row["eve_type"]["name"] for row in rows}
        self.assertEqual({"Revelation", "Naglfar"}, type_names)
        self.assertEqual("Ship", rows[0]["eve_category"]["name"])
        self.assertEqual("Dreadnought", rows[0]["eve_group"]["name"])
        self.assertEqual(4400, rows[0]["eve_group"]["id"])
        self.assertTrue(rows[0]["current_amount"]["srp_value"] > 0)

        history_response = self.client.get(
            f"{BASE_URL}/programs/history",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, history_response.status_code)
        history = history_response.json()
        self.assertEqual(2, len(history))
        rev_rows = [h for h in history if h["program_id"] == rev_program.id]
        self.assertEqual(1, len(rev_rows))
        self.assertEqual(3000000000, rev_rows[0]["srp_value"])

        public_programs = self.client.get(f"{BASE_URL}/programs")
        self.assertEqual(200, public_programs.status_code)
        self.assertEqual(2, len(public_programs.json()))
        public_history = self.client.get(f"{BASE_URL}/programs/history")
        self.assertEqual(200, public_history.status_code)
        self.assertEqual(2, len(public_history.json()))

    def test_get_stats_forbidden_without_permission(self):
        for path in ("stats/overview", "stats/history"):
            with self.subTest(path=path):
                response = self.client.get(
                    f"{BASE_URL}/{path}",
                    HTTP_AUTHORIZATION=f"Bearer {self.token}",
                )
                self.assertEqual(403, response.status_code)

    def test_get_stats_overview_pending_and_average_response_days(self):
        add_user_permission(self.user, "view_evefleetshipreimbursement")
        fc = EveCharacter.objects.create(
            character_id=777001,
            character_name="SRP test",
            user=self.user,
        )
        now = timezone.now()
        EveFleetShipReimbursement.objects.create(
            user=self.user,
            status="pending",
            killmail_id=999000,
            external_killmail_link="https://esi.evetech.net/killmails/999000/abc/",
            character_id=fc.character_id,
            character_name=fc.character_name,
            primary_character_id=fc.character_id,
            primary_character_name=fc.character_name,
            amount=500,
            ship_name="Rifter",
            ship_type_id=123,
        )
        r = EveFleetShipReimbursement.objects.create(
            user=self.user,
            status="approved",
            killmail_id=999001,
            external_killmail_link="https://esi.evetech.net/killmails/999001/abc/",
            character_id=fc.character_id,
            character_name=fc.character_name,
            primary_character_id=fc.character_id,
            primary_character_name=fc.character_name,
            amount=1,
            ship_name="Rifter",
            ship_type_id=123,
            approved_at=now - timedelta(days=5) + timedelta(hours=24),
        )
        EveFleetShipReimbursement.objects.filter(pk=r.pk).update(
            created_at=now - timedelta(days=5),
        )
        response = self.client.get(
            f"{BASE_URL}/stats/overview",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(1, body["pending_requests"])
        self.assertEqual(500, body["pending_total"])
        self.assertAlmostEqual(1.0, body["average_response_days"], places=3)

    def test_get_stats_history_breakdown(self):
        add_user_permission(self.user, "view_evefleetshipreimbursement")
        fc = EveCharacter.objects.create(
            character_id=777002,
            character_name="SRP hist",
            user=self.user,
        )
        cat, _ = EveCategory.objects.get_or_create(
            id=99001, defaults={"name": "Ship", "published": True}
        )
        g_dread, _ = EveGroup.objects.get_or_create(
            id=99002,
            defaults={
                "name": "Dreadnought",
                "published": True,
                "eve_category": cat,
            },
        )
        g_cruiser, _ = EveGroup.objects.get_or_create(
            id=99003,
            defaults={
                "name": "Cruiser",
                "published": True,
                "eve_category": cat,
            },
        )
        t_rev, _ = EveType.objects.get_or_create(
            id=99004,
            defaults={
                "name": "Revelation",
                "published": True,
                "eve_group": g_dread,
            },
        )
        t_stabber, _ = EveType.objects.get_or_create(
            id=99005,
            defaults={
                "name": "Stabber",
                "published": True,
                "eve_group": g_cruiser,
            },
        )
        now = timezone.now()
        base = {
            "user": self.user,
            "character_id": fc.character_id,
            "character_name": fc.character_name,
            "primary_character_id": fc.character_id,
            "primary_character_name": fc.character_name,
        }
        for i, kw in enumerate(
            (
                {
                    "status": "approved",
                    "amount": 100,
                    "ship_name": "Revelation",
                    "ship_type_id": t_rev.id,
                },
                {
                    "status": "rejected",
                    "amount": 50,
                    "ship_name": "Revelation",
                    "ship_type_id": t_rev.id,
                },
                {
                    "status": "approved",
                    "amount": 200,
                    "ship_name": "Stabber",
                    "ship_type_id": t_stabber.id,
                },
            )
        ):
            r = EveFleetShipReimbursement.objects.create(
                **base,
                killmail_id=880000 + i,
                external_killmail_link=(
                    f"https://esi.evetech.net/killmails/{880000 + i}/a/"
                ),
                **kw,
            )
            EveFleetShipReimbursement.objects.filter(pk=r.pk).update(
                created_at=now - timedelta(days=10),
            )

        response = self.client.get(
            f"{BASE_URL}/stats/history?days=30",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(3, body["requests"]["total"])
        self.assertEqual(2, body["requests"]["approved"])
        self.assertEqual(1, body["requests"]["rejected"])
        self.assertEqual(350, body["amounts"]["total"])
        self.assertEqual(300, body["amounts"]["approved"])
        self.assertEqual(50, body["amounts"]["rejected"])

        types_by_id = {t["type_id"]: t for t in body["types"]}
        self.assertEqual(150, types_by_id[t_rev.id]["total"])
        self.assertEqual(100, types_by_id[t_rev.id]["approved"])
        self.assertEqual(50, types_by_id[t_rev.id]["rejected"])
        self.assertEqual(200, types_by_id[t_stabber.id]["total"])

        groups_by_id = {g["group_id"]: g for g in body["groups"]}
        self.assertEqual(150, groups_by_id[g_dread.id]["total"])
        self.assertEqual(200, groups_by_id[g_cruiser.id]["total"])

    def test_get_stats_history_invalid_days(self):
        add_user_permission(self.user, "view_evefleetshipreimbursement")
        response = self.client.get(
            f"{BASE_URL}/stats/history?days=7",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(400, response.status_code)

    def test_resolve_killmail_forbidden_without_add_permission(self):
        response = self.client.post(
            f"{BASE_URL}/resolve-killmail",
            {"external_killmail_link": KM_LINK},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(403, response.status_code)

    @patch("srp.helpers.EsiClient")
    def test_resolve_killmail_returns_candidates(self, esi_mock):
        add_user_permission(self.user, "add_evefleetshipreimbursement")
        esi = esi_mock.return_value
        fc_char = EveCharacter.objects.create(
            character_id=KM_CHAR,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)
        kill_time = timezone.now()
        kill_utc = kill_time.astimezone(dt_timezone.utc)
        esi_killmail_time = kill_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        in_window = make_test_fleet("In window", self.user, start=kill_time)
        cancelled = make_test_fleet("Cancelled", self.user, start=kill_time)
        EveFleet.objects.filter(pk=cancelled.pk).update(status="cancelled")
        late_schedule = make_test_fleet(
            "Late schedule",
            self.user,
            start=kill_time + timedelta(days=3),
        )
        fi = EveFleetInstance.objects.create(
            id=8800112233,
            eve_fleet=late_schedule,
        )
        EveFleetInstance.objects.filter(pk=fi.pk).update(
            start_time=kill_time - timedelta(hours=1),
        )

        esi.get_character_killmail.return_value = EsiResponse(
            response_code=200,
            data={
                "victim": {
                    "character_id": fc_char.character_id,
                    "ship_type_id": 11400,
                },
                "killmail_time": esi_killmail_time,
            },
        )
        esi.get_eve_type.return_value = EveType(
            id=11400,
            name="Jaguar",
            description="Jaguar",
            eve_group=EveGroup(name="ASSAULT_FRIGATE"),
        )

        response = self.client.post(
            f"{BASE_URL}/resolve-killmail",
            {"external_killmail_link": KM_LINK},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(KM_ID, data["killmail_id"])
        self.assertEqual(fc_char.character_id, data["victim_character_id"])
        self.assertEqual(11400, data["ship_type_id"])
        ids = {c["id"] for c in data["candidate_fleets"]}
        self.assertIn(in_window.id, ids)
        self.assertIn(late_schedule.id, ids)
        self.assertNotIn(cancelled.id, ids)
        in_window_row = next(
            c for c in data["candidate_fleets"] if c["id"] == in_window.id
        )
        fc = in_window_row["fleet_commander"]
        self.assertEqual(fc_char.character_id, fc["character_id"])
        self.assertEqual("Mr FC", fc["character_name"])
        self.assertIn("objective", in_window_row)
        self.assertIn("type", in_window_row)

    @patch("srp.helpers.EsiClient")
    def test_resolve_killmail_candidates_for_historical_kill(self, esi_mock):
        """Old killmails must still match fleets in the ±6h window."""
        add_user_permission(self.user, "add_evefleetshipreimbursement")
        esi = esi_mock.return_value
        fc_char = EveCharacter.objects.create(
            character_id=KM_CHAR,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)
        kill_time = timezone.now() - timedelta(days=400)
        kill_utc = kill_time.astimezone(dt_timezone.utc)
        esi_killmail_time = kill_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        historical = make_test_fleet(
            "Historical fleet", self.user, start=kill_time + timedelta(hours=1)
        )
        esi.get_character_killmail.return_value = EsiResponse(
            response_code=200,
            data={
                "victim": {
                    "character_id": fc_char.character_id,
                    "ship_type_id": 11400,
                },
                "killmail_time": esi_killmail_time,
            },
        )
        esi.get_eve_type.return_value = EveType(
            id=11400,
            name="Jaguar",
            description="Jaguar",
            eve_group=EveGroup(name="ASSAULT_FRIGATE"),
        )
        response = self.client.post(
            f"{BASE_URL}/resolve-killmail",
            {"external_killmail_link": KM_LINK},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        ids = {c["id"] for c in response.json()["candidate_fleets"]}
        self.assertIn(historical.id, ids)

    @patch("srp.helpers.EsiClient")
    def test_srp_with_log(self, esi_mock):
        self.make_superuser()
        esi = esi_mock.return_value

        fc_char = EveCharacter.objects.create(
            character_id=KM_CHAR,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc_char)

        esi.get_character_killmail.return_value = EsiResponse(
            response_code=200,
            data={
                "victim": {
                    "character_id": fc_char.character_id,
                    "ship_type_id": 11400,
                },
                "killmail_time": "2025-04-02T11:47:15Z",
            },
        )
        esi.get_eve_type.return_value = EveType(
            id=11400,
            description="Jaguar",
            eve_group=EveGroup(),
        )

        combat_log = CombatLog.objects.create()

        data = {
            "external_killmail_link": KM_LINK,
            "fleet_id": self.fleet.id,
            "is_corp_ship": False,
            "category": "dps",
            "comments": "Testing FTW",
            "combat_log_id": combat_log.id,
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual("dps", data["category"])
        self.assertEqual("Testing FTW", data["comments"])
