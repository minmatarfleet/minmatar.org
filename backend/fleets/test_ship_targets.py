"""Ship targets: lines to start from, ships on no line, Find pilots and the
picker's hangar hints (fleets/helpers/ship_targets.py)."""

from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.models import EveCharacter, EveCharacterAsset
from fittings.models import EveFitting
from fleets.helpers.private_fleet_discord import summary_payload
from fleets.models import EveFleetFitting, EveFleetInvite, EveFleetShipTarget
from fleets.test_private_fleets import (  # noqa: F401 pylint: disable=unused-import
    PrivateFleetTestBase,
    setUpModule,
    tearDownModule,
)
from tribes.tests.publishing_fixtures import make_user

REVELATION, GUARDIAN, LIF, RHEA = 19720, 11987, 37606, 28844
DREADNOUGHT, LOGISTICS, FORCE_AUX, JUMP_FREIGHTER = 485, 832, 1538, 902


def ensure_ship_types():
    ships, _ = EveCategory.objects.get_or_create(
        id=6, defaults={"name": "Ship", "published": True}
    )
    for group_id, group_name, type_id, type_name in (
        (DREADNOUGHT, "Dreadnought", REVELATION, "Revelation"),
        (LOGISTICS, "Logistics", GUARDIAN, "Guardian"),
        (FORCE_AUX, "Force Auxiliary", LIF, "Lif"),
        (JUMP_FREIGHTER, "Jump Freighter", RHEA, "Rhea"),
    ):
        group, _ = EveGroup.objects.get_or_create(
            id=group_id,
            defaults={
                "name": group_name,
                "published": True,
                "eve_category": ships,
            },
        )
        EveType.objects.get_or_create(
            id=type_id,
            defaults={
                "name": type_name,
                "published": True,
                "eve_group": group,
            },
        )


class ShipTargetTestBase(PrivateFleetTestBase):
    def setUp(self):
        super().setUp()
        ensure_ship_types()
        for user in (self.strat, self.pilot, self.outsider):
            EveCharacter.objects.filter(user=user).update(
                alliance_id=MINMATAR_FLEET_ALLIANCE_ID
            )

    def fit(self, fleet, name, ship_id, role="primary"):
        fitting = EveFitting.objects.create(
            name=f"{name} {fleet.id}",
            ship_id=ship_id,
            eft_format=f"[{EveType.objects.get(id=ship_id).name}, {name} {fleet.id}]",
        )
        EveFleetFitting.objects.create(
            eve_fleet=fleet,
            fitting=fitting,
            name=name,
            ship_id=ship_id,
            role=role,
        )

    def line(self, fleet, name, target, types=(), groups=(), order=0):
        return EveFleetShipTarget.objects.create(
            eve_fleet=fleet,
            name=name,
            target=target,
            order=order,
            ship_type_ids=list(types),
            group_ids=list(groups),
        )

    def own(self, user, type_id, location="Amamake - Freeport"):
        character = EveCharacter.objects.filter(user=user).first()
        return EveCharacterAsset.objects.create(
            character=character,
            type_id=type_id,
            type_name=EveType.objects.get(id=type_id).name,
            location_id=1,
            location_name=location,
        )


class SuggestionTests(ShipTargetTestBase):
    def test_one_doctrine_line_per_eve_group_in_role_order(self):
        fleet = self.private_fleet()
        self.fit(fleet, "Revelation Siege", REVELATION, "primary")
        self.fit(fleet, "Siege Logi", GUARDIAN, "support")
        response = self.call(
            "get", f"/{fleet.id}/targets/suggestions", self.strat
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["doctrine"],
            [
                {"name": "Dreadnought", "ship_type_ids": [REVELATION]},
                {"name": "Logistics", "ship_type_ids": [GUARDIAN]},
            ],
        )

    def test_past_fleets_are_only_your_own(self):
        mine = self.private_fleet(
            start_time=timezone.now() - timedelta(days=7)
        )
        self.line(mine, "Dreads", 40, types=[REVELATION])
        other_fc = make_user("other", perms=("view_evefleet",))
        theirs = self.private_fleet(created_by=other_fc)
        self.line(theirs, "Secret", 5, types=[GUARDIAN])
        fleet = self.private_fleet()
        response = self.call(
            "get", f"/{fleet.id}/targets/suggestions", self.strat
        )
        past = response.json()["past_fleets"]
        self.assertEqual([row["fleet_id"] for row in past], [mine.id])
        self.assertEqual(past[0]["lines"][0]["target"], 40)

    def test_pilots_get_no_suggestions(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot)
        response = self.call(
            "get", f"/{fleet.id}/targets/suggestions", self.pilot
        )
        self.assertEqual(response.status_code, 403)


class UnmatchedTests(ShipTargetTestBase):
    def test_lists_hulls_no_line_counts(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot)
        self.line(fleet, "Dreads", 40, groups=[DREADNOUGHT])
        self.volunteer(fleet, self.pilot, ship_type_id=REVELATION)
        self.volunteer(fleet, self.strat, ship_type_id=RHEA)
        response = self.call(
            "get", f"/{fleet.id}/targets/unmatched", self.strat
        )
        self.assertEqual(
            response.json(),
            [{"ship_type_id": RHEA, "ship_name": "Rhea", "characters": 1}],
        )

    def test_nothing_without_targets(self):
        fleet = self.private_fleet()
        self.volunteer(fleet, self.strat, ship_type_id=RHEA)
        response = self.call(
            "get", f"/{fleet.id}/targets/unmatched", self.strat
        )
        self.assertEqual(response.json(), [])


class LineOwnerTests(ShipTargetTestBase):
    def test_lists_members_not_yet_invited_who_own_a_hull(self):
        fleet = self.private_fleet()
        logi = self.line(fleet, "Logistics", 20, groups=[LOGISTICS])
        self.own(self.pilot, GUARDIAN, location="Jita IV - Moon 4")
        self.own(self.outsider, GUARDIAN)
        self.own(self.outsider, REVELATION)
        self.own(self.strat, GUARDIAN)  # the FC is never listed
        response = self.call(
            "get", f"/{fleet.id}/targets/{logi.id}/owners", self.strat
        )
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()
        self.assertEqual(
            [row["user_id"] for row in rows], [self.outsider.id, self.pilot.id]
        )
        self.assertEqual(rows[0]["ship_name"], "Guardian")

    def test_skips_invited_players_and_non_members(self):
        fleet = self.private_fleet()
        logi = self.line(fleet, "Logistics", 20, types=[GUARDIAN])
        self.invite(fleet, self.pilot)
        self.own(self.pilot, GUARDIAN)
        EveCharacter.objects.filter(user=self.outsider).update(alliance_id=1)
        self.own(self.outsider, GUARDIAN)
        response = self.call(
            "get", f"/{fleet.id}/targets/{logi.id}/owners", self.strat
        )
        self.assertEqual(response.json(), [])

    def test_hidden_from_pilots_and_public_fleets(self):
        fleet = self.private_fleet()
        logi = self.line(fleet, "Logistics", 20, types=[GUARDIAN])
        self.invite(fleet, self.pilot)
        response = self.call(
            "get", f"/{fleet.id}/targets/{logi.id}/owners", self.pilot
        )
        self.assertEqual(response.status_code, 404)
        public = self.private_fleet(invite_only=False)
        line = self.line(public, "Logistics", 20, types=[GUARDIAN])
        response = self.call(
            "get", f"/{public.id}/targets/{line.id}/owners", self.strat
        )
        self.assertEqual(response.status_code, 404)

    def test_find_pilots_invites_through_a_wave(self):
        fleet = self.private_fleet()
        logi = self.line(fleet, "Logistics", 20, types=[GUARDIAN])
        self.own(self.outsider, GUARDIAN)
        owners = self.call(
            "get", f"/{fleet.id}/targets/{logi.id}/owners", self.strat
        ).json()
        with patch("discord.outbox.on_commit_enqueue"):
            response = self.call(
                "post",
                f"/{fleet.id}/invites/waves",
                self.strat,
                {"user_ids": [row["user_id"] for row in owners]},
            )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(
            EveFleetInvite.objects.filter(
                eve_fleet=fleet, user=self.outsider
            ).exists()
        )


class MyHangarTests(ShipTargetTestBase):
    def test_lines_by_doctrine_hull_and_owned_hulls(self):
        fleet = self.private_fleet()
        self.fit(fleet, "Revelation Siege", REVELATION, "primary")
        self.fit(fleet, "Siege Logi", GUARDIAN, "support")
        logi = self.line(fleet, "Logistics", 20, groups=[LOGISTICS])
        self.invite(fleet, self.pilot)
        self.own(self.pilot, GUARDIAN)
        self.own(self.pilot, RHEA)  # not in the doctrine: left out
        response = self.call("get", f"/{fleet.id}/targets/mine", self.pilot)
        self.assertEqual(response.status_code, 200, response.content)
        character = EveCharacter.objects.get(user=self.pilot)
        self.assertEqual(
            response.json(),
            {
                "lines_by_ship": [
                    {"ship_type_id": GUARDIAN, "target_id": logi.id}
                ],
                "hangars": [
                    {
                        "character_id": character.character_id,
                        "ship_type_ids": [GUARDIAN],
                    }
                ],
            },
        )

    def test_outsiders_get_404_on_a_private_fleet(self):
        fleet = self.private_fleet()
        response = self.call("get", f"/{fleet.id}/targets/mine", self.outsider)
        self.assertEqual(response.status_code, 404)


class SummaryTests(ShipTargetTestBase):
    def test_thread_summary_says_needed_or_met(self):
        fleet = self.private_fleet()
        self.invite(fleet, self.pilot)
        self.line(fleet, "Dreads", 40, types=[REVELATION], order=0)
        self.line(fleet, "FAX", 1, types=[LIF], order=1)
        self.volunteer(fleet, self.pilot, ship_type_id=LIF)
        fields = summary_payload(fleet)["embeds"][0]["fields"]
        self.assertEqual(
            [field["value"] for field in fields],
            ["0 / 40 · 40 needed", "1 / 1 · ✓ Met"],
        )
