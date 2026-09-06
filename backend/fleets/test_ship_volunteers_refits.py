"""Tests for ship volunteers, fleet refits, and cyno system assignment."""

from datetime import timedelta
from unittest.mock import PropertyMock, patch

from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from discord.models import DiscordUser
from esi.models import Scope, Token

from eveonline.client import SUCCESS, EsiResponse
from eveonline.models import EveCharacter
from fittings.models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
    EveFittingRefit,
)
from fleets.helpers.eft_items import (
    eft_to_dna,
    eft_to_esi_fitting,
    refit_eft_from_swaps,
)
from fleets.helpers.esi_fittings import (
    FITTINGS_SCOPE,
    cleanup_fleet_esi_fittings,
    fitting_publisher,
)
from fleets.helpers.refits import (
    eft_fitted_modules,
    parse_cargo_modules,
    refit_cargo_diff,
)
from fleets.models import (
    EveFleet,
    EveFleetFitting,
    EveFleetFittingRefit,
    EveFleetInstance,
    EveFleetRoleVolunteer,
    EveFleetShipVolunteer,
    _motd_composition,
    _motd_refits,
    _motd_role_volunteers,
)
from fleets.motd import get_motd
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from users.helpers import add_user_permission


def token_for(user):
    """Bearer token for an arbitrary test user."""
    import jwt  # pylint: disable=import-outside-toplevel
    from django.conf import settings  # pylint: disable=import-outside-toplevel

    return jwt.encode(
        {"user_id": user.id}, settings.SECRET_KEY, algorithm="HS256"
    )


def grant_fittings_scope(user, character_id, name):
    """Give ``user`` a character whose ESI token can write fittings."""
    token = Token.objects.create(user=user, character_id=character_id)
    scope, _ = Scope.objects.get_or_create(name=FITTINGS_SCOPE)
    token.scopes.add(scope)
    return EveCharacter.objects.create(
        character_id=character_id,
        character_name=name,
        user=user,
        token=token,
    )


def ensure_hurricane_type():
    """Universe rows so EFT hulls resolve for ESI/DNA (modules optional)."""
    from eveuniverse.models import (  # pylint: disable=import-outside-toplevel
        EveCategory,
        EveGroup,
        EveType,
    )

    category, _ = EveCategory.objects.get_or_create(
        id=6, defaults={"name": "Ship", "published": True}
    )
    group, _ = EveGroup.objects.get_or_create(
        id=419,
        defaults={
            "name": "Combat Battlecruiser",
            "published": True,
            "eve_category": category,
        },
    )
    EveType.objects.get_or_create(
        id=24702,
        defaults={"name": "Hurricane", "published": True, "eve_group": group},
    )


def mock_esi_fittings(test_case, fitting_id=555):
    """Patch EsiClient for fittings; returns the client instance mock."""
    patcher = patch("fleets.helpers.esi_fittings.EsiClient")
    client_cls = patcher.start()
    test_case.addCleanup(patcher.stop)
    client = client_cls.return_value
    client.create_character_fitting.return_value = EsiResponse(
        SUCCESS, data={"fitting_id": fitting_id}
    )
    client.delete_character_fitting.return_value = EsiResponse(SUCCESS)
    return client


BASE_EFT = """[Hurricane, Hurricane [FL33T]]
Damage Control II
Gyrostabilizer II
Gyrostabilizer II
1600mm Steel Plates II
Energized Adaptive Nano Membrane II
Reactive Armor Hardener

50MN Microwarpdrive II
Warp Scrambler II
Stasis Webifier II
Large Cap Battery II

720mm Howitzer Artillery II, Republic Fleet EMP M
720mm Howitzer Artillery II, Republic Fleet EMP M
720mm Howitzer Artillery II, Republic Fleet EMP M
[Empty High slot]

Medium Trimark Armor Pump I
Medium Trimark Armor Pump I
Medium Trimark Armor Pump I

Warrior II x5
Nanite Repair Paste x100
"""

REFIT_EFT = """[Hurricane, Hurricane [FL33T] Cap-stable]
Damage Control II
Gyrostabilizer II
Gyrostabilizer II
1600mm Steel Plates II
Energized Adaptive Nano Membrane II
Reactive Armor Hardener

50MN Microwarpdrive II
Warp Scrambler II
Large Cap Battery II
Large Cap Battery II

720mm Howitzer Artillery II, Republic Fleet EMP M
720mm Howitzer Artillery II, Republic Fleet EMP M
720mm Howitzer Artillery II, Republic Fleet EMP M
Medium Energy Neutralizer II

Medium Trimark Armor Pump I
Medium Trimark Armor Pump I
Medium Trimark Armor Pump I

Warrior II x5
"""


class RefitHelperTestCase(TestCase):
    """Pure helpers for EFT parsing and cargo diffs."""

    def test_eft_fitted_modules_skips_header_empty_and_cargo(self):
        modules = eft_fitted_modules(BASE_EFT)
        self.assertEqual(3, modules["720mm Howitzer Artillery II"])
        self.assertEqual(2, modules["Gyrostabilizer II"])
        self.assertNotIn("Warrior II", modules)
        self.assertNotIn("Nanite Repair Paste", modules)
        self.assertNotIn("[Empty High slot]", modules)
        self.assertNotIn("Hurricane", modules)

    def test_refit_cargo_diff_lists_modules_to_carry(self):
        diff = refit_cargo_diff(BASE_EFT, REFIT_EFT)
        self.assertEqual(
            [("Large Cap Battery II", 1), ("Medium Energy Neutralizer II", 1)],
            diff,
        )

    def test_parse_cargo_modules_merges_quantities(self):
        modules = parse_cargo_modules(
            "Large Cap Battery II x2\n- Stasis Webifier II\n3x Warrior II\n"
            "Large Cap Battery II\n\n"
        )
        self.assertEqual(
            [
                ("Large Cap Battery II", 3),
                ("Stasis Webifier II", 1),
                ("Warrior II", 3),
            ],
            modules,
        )


class MotdRefitsAndCynoTestCase(TestCase):
    def test_motd_renders_refits(self):
        motd = get_motd(
            1,
            "FC",
            None,
            None,
            "https://discord.gg/minmatar",
            "Discord",
            None,
            None,
            role_volunteers=[
                ("Logi FC", [(2, "Anchor")]),
                ("Cynos", [(3, "Cyno One"), (4, "Two")]),
            ],
            refits=[
                ("Cap-stable", "fitting:24702:2048;1::"),
                ("Cargo only", None),
            ],
            composition=[
                ("Ferox Rail Kite", "fitting:16227:2048;1::"),
                ("Plain", None),
            ],
        )
        self.assertIn('<a href="showinfo:1380//3">Cyno One</a>', motd)
        self.assertIn('<a href="showinfo:1380//4">Two</a>', motd)
        # One linked refit per line, no base fit and no cargo steps.
        self.assertIn(
            ">Refits</font>\n"
            '<font size="13" color="#ffffe400">- '
            '<a href="fitting:24702:2048;1::">Cap-stable</a></font>\n'
            '<font size="13" color="#ffffe400">- Cargo only</font>',
            motd,
        )
        self.assertNotIn("Hurricane [FL33T]", motd)
        # Fits header on its own line, one fit per line; in-game links never
        # get <loc>, plain names have no link.
        self.assertIn(
            ">Fits</font>\n"
            '<font size="13" color="#ffffe400">- '
            '<a href="fitting:16227:2048;1::">Ferox Rail Kite</a></font>\n'
            '<font size="13" color="#ffffe400">- Plain</font>',
            motd,
        )
        self.assertNotIn('<loc><a href="fitting:', motd)
        # Blank line after Voice separates fleet info from the ship list.
        self.assertIn("Discord</a></loc></font>\n\n<font", motd)
        # Resources block sits after a blank line.
        self.assertIn(
            '\n\n<font size="13" color="#ffffffff">Resources</font>\n', motd
        )
        self.assertNotIn(">Links<", motd)

    def test_motd_without_refits_has_no_refit_section(self):
        motd = get_motd(1, "FC", None, None, "d", "D", None, None)
        self.assertNotIn("Refits", motd)


class FleetShipVolunteerRefitRouterTestCase(TestCase):
    """HTTP behaviour for ship volunteers, refits and cyno assignment."""

    def setUp(self):
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        super().setUp()
        add_user_permission(self.user, "view_evefleet")

        self.character = EveCharacter.objects.create(
            character_id=1001,
            character_name="Pilot One",
            user=self.user,
        )
        self.fitting = EveFitting.objects.create(
            name="Hurricane [FL33T]",
            ship_id=24702,
            description="",
            eft_format=BASE_EFT,
        )
        self.other_fitting = EveFitting.objects.create(
            name="Scythe [FL33T]",
            ship_id=631,
            description="",
            eft_format="[Scythe, Scythe [FL33T]]\nDamage Control II\n",
        )
        self.refit = EveFittingRefit.objects.create(
            base_fitting=self.fitting,
            name="Cap-stable",
            eft_format=REFIT_EFT,
        )
        self.doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type="non_strategic",
            description="",
        )
        EveDoctrineFitting.objects.create(
            doctrine=self.doctrine, fitting=self.fitting, role="primary"
        )
        # FC owns the fleet; self.user is a regular member by default.
        self.fc_user = User.objects.create(username="fc")
        self.fleet = make_test_fleet("Fleet", self.fc_user)
        self.fleet.doctrine = self.doctrine
        self.fleet.save()
        self.fc_client = Client()
        self.fc_token = token_for(self.fc_user)
        # Refits are saved in-game under the FC: scope + mocked ESI.
        self.fc_character = grant_fittings_scope(self.fc_user, 2001, "FC")
        self.esi = mock_esi_fittings(self)
        ensure_hurricane_type()

    def _auth(self, token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self.token}"}

    # --- ship volunteers -------------------------------------------------

    def _volunteer(self, fitting_id, character_id=1001):
        return self.client.put(
            f"{BASE_URL}/{self.fleet.id}/my-ship-volunteers",
            {
                "selections": [
                    {"character_id": character_id, "fitting_id": fitting_id}
                ]
            },
            "application/json",
            **self._auth(),
        )

    def test_ship_volunteer_lifecycle(self):
        url = f"{BASE_URL}/{self.fleet.id}/ship-volunteers"
        response = self._volunteer(self.fitting.id)
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()[0]
        self.assertEqual("Pilot One", body["character_name"])
        self.assertEqual("Hurricane [FL33T]", body["fitting_name"])
        self.assertEqual(24702, body["ship_id"])

        # idempotent
        response = self._volunteer(self.fitting.id)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, EveFleetShipVolunteer.objects.count())

        response = self.client.get(url, **self._auth())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()))

        volunteer_id = response.json()[0]["id"]
        response = self.client.delete(f"{url}/{volunteer_id}", **self._auth())
        self.assertEqual(204, response.status_code)
        self.assertEqual(0, EveFleetShipVolunteer.objects.count())

    def test_my_pilots_and_bulk_ship_selection(self):
        from fleets.models import (  # pylint: disable=import-outside-toplevel
            EveFleetInstanceMember,
        )

        # Second character, seen in a tracked fleet last week.
        EveCharacter.objects.create(
            character_id=1002, character_name="Pilot Two", user=self.user
        )
        instance = EveFleetInstance.objects.create(
            id=555, eve_fleet=self.fleet, boss_id=1234
        )
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=1002,
            character_name="Pilot Two",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=1,
            ship_name="Rifter",
            solar_system_id=1,
            solar_system_name="X",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(id=member.id).update(
            join_time=timezone.now() - timedelta(days=7)
        )

        url = f"{BASE_URL}/{self.fleet.id}/my-pilots"
        response = self.client.get(url, **self._auth())
        self.assertEqual(200, response.status_code, response.content)
        pilots = response.json()
        self.assertEqual(
            ["Pilot Two", "Pilot One"], [p["character_name"] for p in pilots]
        )
        self.assertTrue(pilots[0]["recent_fleets"])
        self.assertFalse(pilots[1]["recent_fleets"])
        self.assertIsNone(pilots[0]["selection"])

        # Pick a ship for both, then drop one and change the other.
        put_url = f"{BASE_URL}/{self.fleet.id}/my-ship-volunteers"
        response = self.client.put(
            put_url,
            {
                "selections": [
                    {"character_id": 1001, "fitting_id": self.fitting.id},
                    {"character_id": 1002, "fitting_id": self.fitting.id},
                ]
            },
            "application/json",
            **self._auth(),
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(2, len(response.json()))

        response = self.client.put(
            put_url,
            {
                "selections": [
                    {"character_id": 1001},
                    {"character_id": 1002, "fitting_id": self.fitting.id},
                ]
            },
            "application/json",
            **self._auth(),
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([1002], [v["character_id"] for v in response.json()])

        response = self.client.get(url, **self._auth())
        by_id = {p["character_id"]: p for p in response.json()}
        self.assertEqual(
            self.fitting.id, by_id[1002]["selection"]["fitting_id"]
        )
        self.assertIsNone(by_id[1001]["selection"])

        # Someone else's character is refused.
        response = self.client.put(
            put_url,
            {
                "selections": [
                    {"character_id": 4242, "fitting_id": self.fitting.id}
                ]
            },
            "application/json",
            **self._auth(),
        )
        self.assertEqual(400, response.status_code)

    def test_ship_volunteer_rejects_fitting_outside_doctrine(self):
        response = self._volunteer(self.other_fitting.id)
        self.assertEqual(400, response.status_code)
        self.assertIn("composition", response.json()["detail"])

    def test_ship_volunteer_rejects_foreign_character(self):
        response = self._volunteer(self.fitting.id, character_id=4242)
        self.assertEqual(400, response.status_code)

    def test_fc_can_remove_another_users_ship_volunteer(self):
        volunteer = EveFleetShipVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=1001,
            character_name="Pilot One",
            fitting=self.fitting,
        )
        add_user_permission(self.fc_user, "view_evefleet")
        response = self.fc_client.delete(
            f"{BASE_URL}/{self.fleet.id}/ship-volunteers/{volunteer.id}",
            **self._auth(self.fc_token),
        )
        self.assertEqual(204, response.status_code)

    # --- refits ----------------------------------------------------------

    @patch(
        "fleets.endpoints.fleet.post_fleet_refit.try_refresh_active_fleet_motd"
    )
    def test_fc_creates_refit_from_curated_refit_with_derived_cargo(
        self, refresh_mock
    ):
        add_user_permission(self.fc_user, "view_evefleet")
        response = self.fc_client.post(
            f"{BASE_URL}/{self.fleet.id}/refits",
            {"fitting_id": self.fitting.id, "refit_id": self.refit.id},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Cap-stable", body["name"])
        self.assertEqual(self.refit.id, body["refit_id"])
        self.assertEqual(REFIT_EFT, body["eft_format"])
        # Saved in-game under the FC with an identifiable name.
        self.assertEqual(555, body["esi_fitting_id"])
        esi_body = self.esi.create_character_fitting.call_args.args[0]
        self.assertEqual(
            f"MM#{self.fleet.id} Hurricane [FL33T] → Cap-stable",
            esi_body["name"],
        )
        self.assertIn(f"fleet #{self.fleet.id} refit", esi_body["description"])
        self.assertEqual(
            [
                {
                    "name": "Large Cap Battery II",
                    "quantity": 1,
                    "type_id": None,
                },
                {
                    "name": "Medium Energy Neutralizer II",
                    "quantity": 1,
                    "type_id": None,
                },
            ],
            body["modules"],
        )
        refresh_mock.assert_called_once()

    def test_fc_creates_custom_cargo_refit(self):
        add_user_permission(self.fc_user, "view_evefleet")
        url = f"{BASE_URL}/{self.fleet.id}/refits"
        response = self.fc_client.post(
            url,
            {
                "fitting_id": self.fitting.id,
                "name": "Neut refit",
                "cargo_modules": "Medium Energy Neutralizer II x2",
                "notes": "Swap the empty high",
            },
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        refit_id = response.json()["id"]
        self.assertEqual(
            "Medium Energy Neutralizer II x2",
            response.json()["cargo_modules"],
        )

        # Regular members can read but not write.
        response = self.client.get(url, **self._auth())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()))
        response = self.client.delete(f"{url}/{refit_id}", **self._auth())
        self.assertEqual(403, response.status_code)

        response = self.fc_client.delete(
            f"{url}/{refit_id}", **self._auth(self.fc_token)
        )
        self.assertEqual(204, response.status_code)
        self.assertEqual(0, EveFleetFittingRefit.objects.count())

    def test_custom_refit_requires_name(self):
        add_user_permission(self.fc_user, "view_evefleet")
        response = self.fc_client.post(
            f"{BASE_URL}/{self.fleet.id}/refits",
            {"fitting_id": self.fitting.id, "cargo_modules": "Foo"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(400, response.status_code)

    def test_non_fc_cannot_create_refit(self):
        response = self.client.post(
            f"{BASE_URL}/{self.fleet.id}/refits",
            {"fitting_id": self.fitting.id, "refit_id": self.refit.id},
            "application/json",
            **self._auth(),
        )
        self.assertEqual(403, response.status_code)

    def test_motd_refits_helper_builds_lines(self):
        EveFleetFittingRefit.objects.create(
            eve_fleet=self.fleet,
            fitting=self.fitting,
            refit=self.refit,
            name="Cap-stable",
            cargo_modules="Large Cap Battery II x1",
        )
        refits = _motd_refits(self.fleet)
        self.assertEqual([("Cap-stable", None)], refits)  # no EFT, no link

    # --- cyno system assignment -----------------------------------------

    @patch("fleets.helpers.cyno_notifications.DiscordClient")
    def test_fc_assigns_and_clears_cyno_system(self, discord_mock):
        add_user_permission(self.fc_user, "view_evefleet")
        DiscordUser.objects.create(
            id=555, discord_tag="pilot#1", user=self.user
        )
        volunteer = EveFleetRoleVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=1001,
            character_name="Pilot One",
            role=EveFleetRoleVolunteer.ROLE_CYNO,
        )
        url = f"{BASE_URL}/{self.fleet.id}/role-volunteers/{volunteer.id}"

        # Not the FC
        response = self.client.patch(
            url,
            {"solar_system_id": 30003070, "solar_system_name": "Sosala"},
            "application/json",
            **self._auth(),
        )
        self.assertEqual(403, response.status_code)

        response = self.fc_client.patch(
            url,
            {"solar_system_id": 30003070, "solar_system_name": "Sosala"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Sosala", response.json()["solar_system_name"])
        self.assertEqual(30003070, response.json()["solar_system_id"])

        # The pilot got a private DM with the system...
        send_dm = discord_mock.return_value.send_dm
        send_dm.assert_called_once()
        self.assertEqual("555", send_dm.call_args[0][0])
        self.assertIn("Sosala", send_dm.call_args[1]["message"])
        self.assertIn("Pilot One", send_dm.call_args[1]["message"])

        # ...and the MOTD never mentions it.
        cynos = dict(_motd_role_volunteers(self.fleet))["Cynos"]
        self.assertEqual([(1001, "Pilot One")], cynos)
        instance_motd = get_motd(
            1,
            "FC",
            None,
            None,
            "d",
            "D",
            None,
            None,
            role_volunteers=_motd_role_volunteers(self.fleet),
        )
        self.assertNotIn("Sosala", instance_motd)

        # The pilot's own user sees the assignment in the listing...
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/role-volunteers", **self._auth()
        )
        self.assertEqual("Sosala", response.json()[0]["solar_system_name"])

        # ...another member does not.
        other = User.objects.create(username="other")
        add_user_permission(other, "view_evefleet")
        response = Client().get(
            f"{BASE_URL}/{self.fleet.id}/role-volunteers",
            **self._auth(token_for(other)),
        )
        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.json()[0]["solar_system_name"])
        self.assertIsNone(response.json()[0]["solar_system_id"])

        # The FC sees it.
        response = self.fc_client.get(
            f"{BASE_URL}/{self.fleet.id}/role-volunteers",
            **self._auth(self.fc_token),
        )
        self.assertEqual("Sosala", response.json()[0]["solar_system_name"])

        # Clear -> pilot is told the assignment was cleared.
        response = self.fc_client.patch(
            url,
            {"solar_system_id": None, "solar_system_name": None},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.json()["solar_system_name"])
        self.assertEqual(2, send_dm.call_count)
        self.assertIn("cleared", send_dm.call_args[1]["message"])
        cynos = dict(_motd_role_volunteers(self.fleet))["Cynos"]
        self.assertEqual([(1001, "Pilot One")], cynos)

    @patch("fleets.helpers.cyno_notifications.DiscordClient")
    def test_cyno_assignment_without_discord_link_still_saves(
        self, discord_mock
    ):
        add_user_permission(self.fc_user, "view_evefleet")
        volunteer = EveFleetRoleVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=1001,
            character_name="Pilot One",
            role=EveFleetRoleVolunteer.ROLE_CYNO,
        )
        response = self.fc_client.patch(
            f"{BASE_URL}/{self.fleet.id}/role-volunteers/{volunteer.id}",
            {"solar_system_id": 30003070, "solar_system_name": "Sosala"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code)
        volunteer.refresh_from_db()
        self.assertEqual("Sosala", volunteer.solar_system_name)
        discord_mock.return_value.send_dm.assert_not_called()

    def test_system_assignment_only_for_cynos(self):
        add_user_permission(self.fc_user, "view_evefleet")
        volunteer = EveFleetRoleVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=1001,
            character_name="Pilot One",
            role=EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR,
        )
        response = self.fc_client.patch(
            f"{BASE_URL}/{self.fleet.id}/role-volunteers/{volunteer.id}",
            {"solar_system_id": 30003070, "solar_system_name": "Sosala"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(400, response.status_code)


class FleetCompositionRouterTestCase(TestCase):
    """Makeshift doctrines (catalog picks) and manual EFT fits per fleet."""

    def setUp(self):
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        super().setUp()
        add_user_permission(self.user, "view_evefleet")

        from eveuniverse.models import (  # pylint: disable=import-outside-toplevel
            EveCategory,
            EveGroup,
            EveType,
        )

        category, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=419,
            defaults={
                "name": "Combat Battlecruiser",
                "published": True,
                "eve_category": category,
            },
        )
        EveType.objects.get_or_create(
            id=24702,
            defaults={
                "name": "Hurricane",
                "published": True,
                "eve_group": group,
            },
        )
        EveType.objects.get_or_create(
            id=16227,
            defaults={"name": "Ferox", "published": True, "eve_group": group},
        )

        self.character = EveCharacter.objects.create(
            character_id=1001, character_name="Pilot One", user=self.user
        )
        self.catalog_fitting = EveFitting.objects.create(
            name="Hurricane [FL33T]",
            ship_id=24702,
            description="",
            eft_format=BASE_EFT,
        )
        # FC owns the fleet; no doctrine set on purpose.
        self.fc_user = User.objects.create(username="fc")
        add_user_permission(self.fc_user, "view_evefleet")
        self.fleet = make_test_fleet("Fleet", self.fc_user)
        self.fc_client = Client()
        self.fc_token = token_for(self.fc_user)
        self.fc_character = grant_fittings_scope(self.fc_user, 2001, "FC")
        self.esi = mock_esi_fittings(self)

    def _auth(self, token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self.token}"}

    def test_patch_with_null_doctrine_unsets_it(self):
        add_user_permission(self.fc_user, "add_evefleet")
        doctrine = EveDoctrine.objects.create(
            name="Temp", type="non_strategic", description=""
        )
        self.fleet.doctrine = doctrine
        self.fleet.save()
        url = f"{BASE_URL}/{self.fleet.id}"
        # Omitting the field leaves the doctrine alone.
        response = self.fc_client.patch(
            url,
            {"description": "x"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(doctrine.id, response.json()["doctrine_id"])
        # "No doctrine" sends an explicit null.
        response = self.fc_client.patch(
            url,
            {"doctrine_id": None},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(response.json()["doctrine_id"])
        self.fleet.refresh_from_db()
        self.assertIsNone(self.fleet.doctrine_id)

    def test_composition_empty_without_doctrine_or_fittings(self):
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/composition", **self._auth()
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def test_fc_builds_makeshift_doctrine_and_manual_fit(self):
        url = f"{BASE_URL}/{self.fleet.id}/fittings"

        # Members cannot add fittings.
        response = self.client.post(
            url,
            {"fitting_id": self.catalog_fitting.id},
            "application/json",
            **self._auth(),
        )
        self.assertEqual(403, response.status_code)

        # Catalog pick
        response = self.fc_client.post(
            url,
            {"fitting_id": self.catalog_fitting.id, "role": "primary"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        catalog_entry = response.json()
        self.assertEqual("catalog", catalog_entry["source"])
        self.assertEqual({}, catalog_entry["module_slots"])
        self.assertEqual(self.catalog_fitting.id, catalog_entry["fitting_id"])
        self.assertEqual("Hurricane", catalog_entry["ship_name"])
        self.assertEqual("Combat Battlecruiser", catalog_entry["ship_group"])

        # Duplicate catalog pick is rejected
        response = self.fc_client.post(
            url,
            {"fitting_id": self.catalog_fitting.id},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(400, response.status_code)

        # Manual EFT fit
        manual_eft = (
            "[Ferox, Ferox Rail Kite]\nDamage Control II\n\n"
            "50MN Microwarpdrive II\n\n250mm Railgun II, Spike M\n"
        )
        response = self.fc_client.post(
            url,
            {"eft_format": manual_eft, "role": "support"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        manual_entry = response.json()
        self.assertEqual("manual", manual_entry["source"])
        self.assertIsNone(manual_entry["fitting_id"])
        self.assertEqual(16227, manual_entry["ship_id"])
        self.assertEqual("Ferox Rail Kite", manual_entry["name"])
        self.assertEqual([], manual_entry["refits"])
        stored = EveFleetFitting.objects.get(
            id=manual_entry["fleet_fitting_id"]
        )
        self.assertEqual(555, stored.esi_fitting_id)
        self.assertEqual(2001, stored.esi_character_id)
        esi_body = self.esi.create_character_fitting.call_args.args[0]
        self.assertEqual(
            f"MM#{self.fleet.id} Ferox Rail Kite", esi_body["name"]
        )
        self.assertEqual(16227, esi_body["ship_type_id"])

        # Unknown hull is rejected
        response = self.fc_client.post(
            url,
            {"eft_format": "[Notaship, Weird]\nDamage Control II\n"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(400, response.status_code)

        # Composition lists both, primary first
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/composition", **self._auth()
        )
        keys = [e["key"] for e in response.json()]
        self.assertEqual(
            [
                f"f:{self.catalog_fitting.id}",
                f"m:{manual_entry['fleet_fitting_id']}",
            ],
            keys,
        )

        # MOTD shows the fleet-specific fits instead of "Set the doctrine"
        composition = _motd_composition(self.fleet)
        self.assertEqual(2, len(composition))
        motd = get_motd(
            1,
            "FC",
            None,
            None,
            "d",
            "D",
            None,
            None,
            fleet_edit_url="https://x/edit",
            composition=composition,
        )
        self.assertIn(">Fits</font>", motd)
        self.assertIn(
            '- <a href="fitting:24702::">Hurricane [FL33T]</a></font>\n'
            '<font size="13" color="#ffffe400">- '
            '<a href="fitting:16227::">Ferox Rail Kite</a>',
            motd,
        )
        self.assertNotIn("Set the doctrine", motd)

        # One character brings the manual fit, another the catalog fit
        EveCharacter.objects.create(
            character_id=1002, character_name="Pilot Two", user=self.user
        )
        response = self.client.put(
            f"{BASE_URL}/{self.fleet.id}/my-ship-volunteers",
            {
                "selections": [
                    {
                        "character_id": 1001,
                        "fleet_fitting_id": manual_entry["fleet_fitting_id"],
                    },
                    {
                        "character_id": 1002,
                        "fitting_id": self.catalog_fitting.id,
                    },
                ]
            },
            "application/json",
            **self._auth(),
        )
        self.assertEqual(200, response.status_code, response.content)
        by_character = {v["character_id"]: v for v in response.json()}
        self.assertEqual("Ferox Rail Kite", by_character[1001]["fitting_name"])
        self.assertEqual(16227, by_character[1001]["ship_id"])
        self.assertEqual(2, EveFleetShipVolunteer.objects.count())

        # Custom refit on the manual fit
        response = self.fc_client.post(
            f"{BASE_URL}/{self.fleet.id}/refits",
            {
                "fleet_fitting_id": manual_entry["fleet_fitting_id"],
                "name": "Blaster swap",
                "cargo_modules": "Heavy Neutron Blaster II x7",
            },
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Ferox Rail Kite", response.json()["fitting_name"])
        # Curated refits do not exist for manual fits
        response = self.fc_client.post(
            f"{BASE_URL}/{self.fleet.id}/refits",
            {
                "fleet_fitting_id": manual_entry["fleet_fitting_id"],
                "refit_id": 1,
            },
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(400, response.status_code)

        # Removing the manual fit cascades its volunteers and refits
        response = self.fc_client.delete(
            f"{url}/{manual_entry['fleet_fitting_id']}",
            **self._auth(self.fc_token),
        )
        self.assertEqual(204, response.status_code)
        self.assertEqual(1, EveFleetShipVolunteer.objects.count())
        self.assertEqual(0, EveFleetFittingRefit.objects.count())

    def test_supply_reports_contracts_and_market_per_ship(self):
        from eveuniverse.models import (  # pylint: disable=import-outside-toplevel
            EveType,
        )
        from market.models import (  # pylint: disable=import-outside-toplevel
            EveMarketItemOrder,
        )
        from fleets.helpers.supply import (  # pylint: disable=import-outside-toplevel
            eft_purchase_items,
        )

        needed = eft_purchase_items(BASE_EFT)
        self.assertEqual(1, needed["Hurricane"])
        self.assertEqual(3, needed["720mm Howitzer Artillery II"])
        self.assertNotIn("Warrior II", needed)
        self.assertNotIn("Republic Fleet EMP M", needed)

        self.fc_client.post(
            f"{BASE_URL}/{self.fleet.id}/fittings",
            {"fitting_id": self.catalog_fitting.id},
            "application/json",
            **self._auth(self.fc_token),
        )

        # No sell orders at staging yet -> market data absent.
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/supply", **self._auth()
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, len(body["entries"]))
        self.assertEqual(0, body["entries"][0]["contracts"])
        self.assertIsNone(body["entries"][0]["market_fits"])

        # Stock the hull only: the fit is not buyable and the gaps are named.
        hull = EveType.objects.get(name="Hurricane")
        EveMarketItemOrder.objects.create(
            order_id=1,
            item=hull,
            location=self.fleet.location,
            price=1,
            quantity=4,
            is_buy_order=False,
        )
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/supply", **self._auth()
        )
        entry = response.json()["entries"][0]
        self.assertEqual(0, entry["market_fits"])
        self.assertIn("720mm Howitzer Artillery II", entry["market_missing"])
        self.assertNotIn("Hurricane", entry["market_missing"])

    def test_my_fittings_remembers_custom_efts(self):
        manual_eft = "[Ferox, Ferox Rail Kite]\nDamage Control II\n"
        for _ in range(2):  # same fit on two fleets collapses to one entry
            self.fc_client.post(
                f"{BASE_URL}/{self.fleet.id}/fittings",
                {"eft_format": manual_eft, "role": "support"},
                "application/json",
                **self._auth(self.fc_token),
            )
            self.fleet = make_test_fleet("Another", self.fc_user)
        response = self.fc_client.get(
            f"{BASE_URL}/my-fittings", **self._auth(self.fc_token)
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, len(body))
        self.assertEqual("Ferox Rail Kite", body[0]["name"])
        self.assertEqual("Ferox", body[0]["ship_name"])
        self.assertIn("Damage Control II", body[0]["eft_format"])

        # Other users don't see the FC's fits.
        response = self.client.get(f"{BASE_URL}/my-fittings", **self._auth())
        self.assertEqual([], response.json())

    def test_fleet_fittings_merge_with_doctrine(self):
        doctrine = EveDoctrine.objects.create(
            name="Doc", type="non_strategic", description=""
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=self.catalog_fitting, role="primary"
        )
        self.fleet.doctrine = doctrine
        self.fleet.save()
        extra = EveFitting.objects.create(
            name="Scythe [FL33T]",
            ship_id=631,
            description="",
            eft_format="[Scythe, Scythe [FL33T]]\nDamage Control II\n",
        )
        response = self.fc_client.post(
            f"{BASE_URL}/{self.fleet.id}/fittings",
            {"fitting_id": extra.id, "role": "support"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)

        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/composition", **self._auth()
        )
        sources = [(e["source"], e["fitting_id"]) for e in response.json()]
        self.assertEqual(
            [("doctrine", self.catalog_fitting.id), ("catalog", extra.id)],
            sources,
        )
        # With a doctrine the MOTD keeps the doctrine link, no Fits section
        self.assertEqual([], _motd_composition(self.fleet))


class EsiFittingsTestCase(TestCase):
    """EFT → ESI items / DNA, slot-swap refits, scope guard and cleanup."""

    def setUp(self):
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        super().setUp()
        add_user_permission(self.user, "view_evefleet")

        from eveuniverse.models import (  # pylint: disable=import-outside-toplevel
            EveCategory,
            EveDogmaEffect,
            EveGroup,
            EveType,
            EveTypeDogmaEffect,
        )

        def make_type(type_id, name, group_id, category_id, effect=None):
            category, _ = EveCategory.objects.get_or_create(
                id=category_id,
                defaults={"name": f"cat{category_id}", "published": True},
            )
            group, _ = EveGroup.objects.get_or_create(
                id=group_id,
                defaults={
                    "name": f"group{group_id}",
                    "published": True,
                    "eve_category": category,
                },
            )
            eve_type, _ = EveType.objects.get_or_create(
                id=type_id,
                defaults={"name": name, "published": True, "eve_group": group},
            )
            if effect:
                dogma, _ = EveDogmaEffect.objects.get_or_create(
                    id=effect, defaults={"name": f"effect{effect}"}
                )
                EveTypeDogmaEffect.objects.get_or_create(
                    eve_type=eve_type,
                    eve_dogma_effect=dogma,
                    defaults={"is_default": False},
                )
            return eve_type

        make_type(24702, "Hurricane", 419, 6)
        make_type(2048, "Damage Control II", 60, 7, effect=11)  # low
        make_type(519, "Gyrostabilizer II", 59, 7, effect=11)
        make_type(12076, "50MN Microwarpdrive II", 46, 7, effect=13)  # mid
        make_type(3504, "Large Cap Battery II", 61, 7, effect=13)
        make_type(2961, "720mm Howitzer Artillery II", 55, 7, effect=12)
        make_type(21740, "Republic Fleet EMP M", 83, 8)  # charge
        make_type(31055, "Medium Trimark Armor Pump I", 773, 7, effect=2663)
        make_type(2488, "Warrior II", 100, 18)  # drone
        make_type(28668, "Nanite Repair Paste", 1, 8)  # cargo

        self.eft = (
            "[Hurricane, Test]\n"
            "Damage Control II\n"
            "Gyrostabilizer II\n"
            "Gyrostabilizer II\n"
            "[Empty Low slot]\n\n"
            "50MN Microwarpdrive II\n\n"
            "720mm Howitzer Artillery II, Republic Fleet EMP M\n"
            "Unknown Module Name\n\n"
            "Medium Trimark Armor Pump I\n\n"
            "Warrior II x5\n"
            "Nanite Repair Paste x100\n"
            "Large Cap Battery II x2\n"
        )

        self.fitting = EveFitting.objects.create(
            name="Hurricane [FL33T]",
            ship_id=24702,
            description="",
            eft_format=self.eft,
        )
        self.doctrine = EveDoctrine.objects.create(
            name="Doctrine", type="non_strategic", description=""
        )
        EveDoctrineFitting.objects.create(
            doctrine=self.doctrine, fitting=self.fitting, role="primary"
        )
        self.fc_user = User.objects.create(username="fc")
        add_user_permission(self.fc_user, "view_evefleet")
        self.fleet = make_test_fleet("Fleet", self.fc_user)
        self.fleet.doctrine = self.doctrine
        self.fleet.save()
        self.fc_client = Client()
        self.fc_token = token_for(self.fc_user)
        self.esi = mock_esi_fittings(self)

    def _auth(self, token=None):
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self.token}"}

    # --- pure helpers ----------------------------------------------------

    def test_eft_to_esi_fitting_assigns_slots_bays_and_cargo(self):
        ship_id, items = eft_to_esi_fitting(self.eft)
        self.assertEqual(24702, ship_id)
        flags = {(i["type_id"], i["flag"]): i["quantity"] for i in items}
        self.assertEqual(1, flags[(2048, "LoSlot0")])
        self.assertEqual(1, flags[(519, "LoSlot1")])
        self.assertEqual(1, flags[(519, "LoSlot2")])
        self.assertEqual(1, flags[(12076, "MedSlot0")])
        self.assertEqual(1, flags[(2961, "HiSlot0")])
        # Loaded charge shares the launcher's slot.
        self.assertEqual(1, flags[(21740, "HiSlot0")])
        self.assertEqual(1, flags[(31055, "RigSlot0")])
        self.assertEqual(5, flags[(2488, "DroneBay")])
        self.assertEqual(100, flags[(28668, "Cargo")])
        self.assertEqual(2, flags[(3504, "Cargo")])
        # Unknown names are dropped, not guessed.
        self.assertEqual(10, len(items))

    def test_eft_to_esi_fitting_unknown_hull(self):
        self.assertEqual((None, []), eft_to_esi_fitting("[Nope, x]\nDCU\n"))

    def test_eft_to_dna_marks_cargo_with_underscore(self):
        dna = eft_to_dna(self.eft)
        self.assertTrue(dna.startswith("24702:"))
        self.assertTrue(dna.endswith("::"))
        self.assertIn(":519;2:", dna)  # fitted modules merged by type
        self.assertIn(":2488_;5:", dna)  # drones as cargo-style items
        self.assertIn(":3504_;2", dna)

    def test_refit_eft_from_swaps_replaces_slot_and_updates_cargo(self):
        eft, err = refit_eft_from_swaps(
            self.eft,
            [("50MN Microwarpdrive II", "Large Cap Battery II")],
            "Cap-stable",
        )
        self.assertIsNone(err)
        self.assertTrue(eft.startswith("[Hurricane, Cap-stable]\n"))
        self.assertIn("\nLarge Cap Battery II\n", eft)
        self.assertNotIn("\n50MN Microwarpdrive II\n", eft)
        # One battery left in cargo, the MWD moves to cargo.
        self.assertIn("Large Cap Battery II x1", eft)
        self.assertIn("50MN Microwarpdrive II x1", eft)
        self.assertIn("Warrior II x5", eft)

    def test_refit_eft_from_swaps_rejects_slot_mismatch(self):
        _, err = refit_eft_from_swaps(
            self.eft, [("Damage Control II", "Large Cap Battery II")], "x"
        )
        self.assertIn("does not fit a low slot", err)

    def test_refit_eft_from_swaps_rejects_more_than_carried(self):
        _, err = refit_eft_from_swaps(
            self.eft,
            [
                ("50MN Microwarpdrive II", "Large Cap Battery II"),
                ("Gyrostabilizer II", "Large Cap Battery II"),
                ("Gyrostabilizer II", "Large Cap Battery II"),
            ],
            "x",
        )
        self.assertIn("Only 2 x Large Cap Battery II", err)

    def test_refit_eft_from_swaps_rejects_unfitted_module(self):
        _, err = refit_eft_from_swaps(
            self.eft, [("Stasis Webifier II", "Large Cap Battery II")], "x"
        )
        self.assertIn("not fitted", err)

    # --- scope guard -------------------------------------------------------

    def test_refit_and_manual_fit_require_fittings_scope(self):
        self.assertIsNone(fitting_publisher(self.fc_user))
        response = self.fc_client.get(
            f"{BASE_URL}/{self.fleet.id}/fitting-access",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(response.json()["can_publish"])
        self.assertEqual(FITTINGS_SCOPE, response.json()["scope"])
        self.assertEqual("FleetCommander", response.json()["token_type"])

        response = self.fc_client.post(
            f"{BASE_URL}/{self.fleet.id}/refits",
            {
                "fitting_id": self.fitting.id,
                "swaps": [
                    {
                        "module_out": "50MN Microwarpdrive II",
                        "module_in": "Large Cap Battery II",
                    }
                ],
            },
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(400, response.status_code)
        self.assertIn(FITTINGS_SCOPE, response.json()["detail"])

        response = self.fc_client.post(
            f"{BASE_URL}/{self.fleet.id}/fittings",
            {"eft_format": self.eft, "role": "support"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(400, response.status_code)
        self.assertIn(FITTINGS_SCOPE, response.json()["detail"])
        self.esi.create_character_fitting.assert_not_called()

        # Members never see the access endpoint.
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/fitting-access", **self._auth()
        )
        self.assertEqual(403, response.status_code)

        grant_fittings_scope(self.fc_user, 2001, "FC")
        response = self.fc_client.get(
            f"{BASE_URL}/{self.fleet.id}/fitting-access",
            **self._auth(self.fc_token),
        )
        self.assertTrue(response.json()["can_publish"])

    def test_swap_refit_is_published_and_cleaned_up(self):
        grant_fittings_scope(self.fc_user, 2001, "FC")
        url = f"{BASE_URL}/{self.fleet.id}/refits"
        response = self.fc_client.post(
            url,
            {
                "fitting_id": self.fitting.id,
                "swaps": [
                    {
                        "module_out": "50MN Microwarpdrive II",
                        "module_in": "Large Cap Battery II",
                    }
                ],
            },
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Large Cap Battery II", body["name"])
        self.assertEqual("Large Cap Battery II x1", body["cargo_modules"])
        self.assertEqual(
            "50MN Microwarpdrive II → Large Cap Battery II", body["notes"]
        )
        self.assertIn("[Hurricane, Large Cap Battery II]", body["eft_format"])
        self.assertEqual(555, body["esi_fitting_id"])

        esi_body = self.esi.create_character_fitting.call_args.args[0]
        self.assertEqual(24702, esi_body["ship_type_id"])
        self.assertTrue(esi_body["name"].startswith(f"MM#{self.fleet.id} "))
        self.assertLessEqual(len(esi_body["name"]), 50)
        self.assertIn(
            {"type_id": 3504, "flag": "MedSlot0", "quantity": 1},
            esi_body["items"],
        )

        # MOTD links the refit in-game.
        _, href = _motd_refits(self.fleet)[0]
        self.assertTrue(href.startswith("fitting:24702:"))
        self.assertIn("3504;1", href)

        # Closing the fleet deletes what we created.
        add_user_permission(self.fc_user, "add_evefleet")
        response = self.fc_client.patch(
            f"{BASE_URL}/{self.fleet.id}",
            {"status": "complete"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        self.esi.delete_character_fitting.assert_called_once_with(555)
        refit = EveFleetFittingRefit.objects.get(id=body["id"])
        self.assertIsNone(refit.esi_fitting_id)
        self.assertIsNone(refit.esi_character_id)

    def test_removing_a_refit_deletes_the_in_game_fitting(self):
        grant_fittings_scope(self.fc_user, 2001, "FC")
        url = f"{BASE_URL}/{self.fleet.id}/refits"
        response = self.fc_client.post(
            url,
            {
                "fitting_id": self.fitting.id,
                "swaps": [
                    {
                        "module_out": "50MN Microwarpdrive II",
                        "module_in": "Large Cap Battery II",
                    }
                ],
            },
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        response = self.fc_client.delete(
            f"{url}/{response.json()['id']}", **self._auth(self.fc_token)
        )
        self.assertEqual(204, response.status_code)
        self.esi.delete_character_fitting.assert_called_once_with(555)

    def test_cleanup_tolerates_esi_failures(self):
        grant_fittings_scope(self.fc_user, 2001, "FC")
        fitting = EveFleetFitting.objects.create(
            eve_fleet=self.fleet,
            name="Custom",
            ship_id=24702,
            eft_format=self.eft,
            esi_fitting_id=900,
            esi_character_id=2001,
        )
        gone = EveFleetFitting.objects.create(
            eve_fleet=self.fleet,
            name="Gone",
            ship_id=24702,
            eft_format=self.eft,
            esi_fitting_id=901,
            esi_character_id=2001,
        )
        self.esi.delete_character_fitting.side_effect = [
            EsiResponse(500, response="boom"),
            EsiResponse(404),
        ]
        self.assertEqual(1, cleanup_fleet_esi_fittings(self.fleet))
        fitting.refresh_from_db()
        gone.refresh_from_db()
        self.assertEqual(900, fitting.esi_fitting_id)  # retried next close
        self.assertIsNone(gone.esi_fitting_id)  # 404 counts as done

    def test_esi_failure_on_create_keeps_the_refit(self):
        grant_fittings_scope(self.fc_user, 2001, "FC")
        self.esi.create_character_fitting.return_value = EsiResponse(
            420, response="rate limited"
        )
        response = self.fc_client.post(
            f"{BASE_URL}/{self.fleet.id}/fittings",
            {"eft_format": self.eft, "role": "support"},
            "application/json",
            **self._auth(self.fc_token),
        )
        self.assertEqual(200, response.status_code, response.content)
        stored = EveFleetFitting.objects.get(eve_fleet=self.fleet)
        self.assertIsNone(stored.esi_fitting_id)
        # The MOTD still links the fit via DNA.
        name, href = _motd_composition_for(self.fleet)
        self.assertEqual("Test", name)
        self.assertTrue(href.startswith("fitting:24702:"))


class MotdLengthTestCase(TestCase):
    """DNA links are long; the MOTD must still fit ESI's cap."""

    def test_composition_falls_back_to_web_links_when_too_long(self):
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        ensure_hurricane_type()
        fc_user = User.objects.create(username="fc-long")
        fc_character = EveCharacter.objects.create(
            character_id=3001, character_name="Long FC", user=fc_user
        )
        fleet = make_test_fleet("Fleet", fc_user)
        catalog = EveFitting.objects.create(
            name="Hurricane [FL33T]",
            ship_id=24702,
            description="",
            eft_format=BASE_EFT,
        )
        EveFleetFitting.objects.create(
            eve_fleet=fleet, fitting=catalog, name=catalog.name, ship_id=24702
        )
        # Very long names push a MOTD over the cap without refits at all.
        for i in range(12):
            EveFleetFitting.objects.create(
                eve_fleet=fleet,
                name=f"Custom {i} " + "x" * 250,
                ship_id=24702,
                eft_format="[Hurricane, Custom]\nDamage Control II\n",
            )
        instance = EveFleetInstance.objects.create(id=99, eve_fleet=fleet)
        with patch.object(
            EveFleet,
            "fleet_commander",
            new_callable=PropertyMock,
            return_value=fc_character,
        ):
            motd = instance.build_motd()
        # Web link kept for the catalog fit, DNA links dropped.
        self.assertIn(f"/ships/fittings/{catalog.id}", motd)
        self.assertNotIn('href="fitting:', motd)


def _motd_composition_for(fleet):
    fleet.doctrine = None
    fleet.save()
    return _motd_composition(fleet)[0]
