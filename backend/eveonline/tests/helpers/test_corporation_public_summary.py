"""Aggregate public corporation About stats."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from eveonline.helpers.corporations.summary import corporation_public_summary
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCorporation,
)
from fleets.models import (
    EveFleet,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)
from groups.models import UserCommunityStatus

BASE_URL = "/api/eveonline/corporations/"


def _disconnect_external_signals():
    signals.post_save.disconnect(
        sender=EveCharacter,
        dispatch_uid="populate_eve_character_public_data",
    )
    signals.post_save.disconnect(
        sender=EveCharacter,
        dispatch_uid="populate_eve_character_private_data",
    )
    signals.post_save.disconnect(
        sender=EveFleet,
        dispatch_uid="update_fleet_schedule_on_save",
    )
    signals.post_save.disconnect(
        sender=Group,
        dispatch_uid="group_post_save",
    )
    signals.post_save.disconnect(
        sender=UserCommunityStatus,
        dispatch_uid="user_community_status_post_save",
    )


class CorporationPublicSummaryTestCase(TestCase):
    def setUp(self):
        _disconnect_external_signals()
        super().setUp()
        self.client = Client()
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134,
            name="Rattini Tribe",
            biography="Bio",
        )
        self.groups = _ship_groups()

    def test_community_counts_humans_not_alts(self):
        self._status_user("active-pilot", UserCommunityStatus.STATUS_ACTIVE)
        self._character(101, "Alt One", self.user)
        self._character(102, "Alt Two", self.user)
        trial = self._status_user("trial-pilot", "trial")
        self._character(103, "Trial Pilot", trial)
        on_leave = self._status_user("leave-pilot", "on_leave")
        self._character(104, "Leave Pilot", on_leave)
        unstatused = User.objects.create_user(username="plain-pilot")
        self._character(105, "Plain Pilot", unstatused)
        self._character(106, "Unlinked Pilot", None)

        summary = corporation_public_summary(self.corporation)
        community = summary["community"]
        self.assertEqual(4, community["humans"])
        self.assertEqual(
            [
                {"key": "active", "count": 1},
                {"key": "trial", "count": 1},
                {"key": "on_leave", "count": 1},
            ],
            community["slices"],
        )

    def test_fleet_tiers_count_distinct_instances_per_human(self):
        regular = User.objects.create_user(username="regular-pilot")
        occasional = User.objects.create_user(username="occasional-pilot")
        core = User.objects.create_user(username="core-pilot")
        absent = User.objects.create_user(username="absent-pilot")
        main = self._character(201, "Regular Main", regular)
        alt = self._character(202, "Regular Alt", regular)
        occasional_char = self._character(203, "Occasional", occasional)
        core_char = self._character(204, "Core", core)
        self._character(205, "Absent", absent)

        self._attend(main, 1, self.groups["battleship"])
        self._attend(alt, 1, self.groups["battleship"])
        for instance_id in (2, 3, 4):
            self._attend(main, instance_id, self.groups["battleship"])
        self._attend(occasional_char, 5, self.groups["interceptor"])
        for instance_id in range(6, 16):
            self._attend(core_char, instance_id, self.groups["dreadnought"])
        old = self._attend(main, 99, self.groups["battleship"])
        EveFleetInstanceMember.objects.filter(pk=old.pk).update(
            join_time=timezone.now() - timedelta(days=200)
        )

        summary = corporation_public_summary(self.corporation)
        fleets = summary["fleet_participation"]
        self.assertEqual(15, fleets["fleet_instances"])
        self.assertEqual(
            [
                {"key": "inactive", "count": 1},
                {"key": "lapsing", "count": 1},
                {"key": "regular", "count": 1},
                {"key": "core", "count": 1},
            ],
            fleets["slices"],
        )

    @patch(
        "eveonline.helpers.corporations.summary.observed_prime_buckets_for_users",
        return_value={},
    )
    def test_pilots_without_active_timezone_count_as_on_leave(
        self, observed_mock
    ):
        pilot = User.objects.create_user(username="tzless-pilot")
        character = self._character(206, "Tzless", pilot)
        for instance_id in range(20, 24):
            self._attend(character, instance_id, self.groups["battleship"])

        summary = corporation_public_summary(self.corporation)
        self.assertEqual(
            [{"key": "inactive", "count": 1}],
            summary["fleet_participation"]["slices"],
        )

    def test_ship_buckets_use_fleet_hulls_and_skip_capsules(self):
        pilot = self._character(301, "Ship Pilot", self.user)
        podded = self._attend(pilot, 1, self.groups["capsule"])
        EveFleetInstanceMemberShipSnapshot.objects.create(
            member=podded,
            ship_type_id=self.groups["battleship"],
            ship_name="Tempest",
            solar_system_id=1,
            solar_system_name="Amamake",
        )
        self._attend(pilot, 2, self.groups["logistics"])
        self._attend(pilot, 3, self.groups["interceptor"])
        self._attend(pilot, 4, self.groups["dreadnought"])
        self._attend(pilot, 5, self.groups["industrial"])
        self._attend(pilot, 6, self.groups["shuttle"])

        summary = corporation_public_summary(self.corporation)
        ships = summary["fleet_ships"]
        self.assertEqual(4, ships["pilot_fleets"])
        self.assertEqual(
            [
                {"key": "dps", "count": 1},
                {"key": "logistics", "count": 1},
                {"key": "support", "count": 1},
                {"key": "capital", "count": 1},
            ],
            ships["slices"],
        )

    def test_ship_roles_count_each_person_once_per_fleet(self):
        boxer = User.objects.create_user(username="boxer")
        main = self._character(311, "Boxer Main", boxer)
        alt = self._character(312, "Boxer Logi Alt", boxer)
        solo = self._character(313, "Solo Pilot", self.user)
        self._attend(main, 1, self.groups["battleship"])
        self._attend(alt, 1, self.groups["logistics"])
        self._attend(solo, 1, self.groups["battleship"])

        ships = corporation_public_summary(self.corporation)["fleet_ships"]
        self.assertEqual(2, ships["pilot_fleets"])
        self.assertEqual(
            [
                {"key": "dps", "count": 1.5},
                {"key": "logistics", "count": 0.5},
            ],
            ships["slices"],
        )

    def test_reshipping_into_same_role_counts_once(self):
        pilot = self._character(321, "Reshipper", self.user)
        member = self._attend(pilot, 1, self.groups["battleship"])
        EveFleetInstanceMemberShipSnapshot.objects.create(
            member=member,
            ship_type_id=self.groups["battleship_two"],
            ship_name="Typhoon",
            solar_system_id=1,
            solar_system_name="Amamake",
        )
        EveFleetInstanceMemberShipSnapshot.objects.create(
            member=member,
            ship_type_id=self.groups["battleship"],
            ship_name="Tempest",
            solar_system_id=1,
            solar_system_name="Amamake",
        )

        ships = corporation_public_summary(self.corporation)["fleet_ships"]
        self.assertEqual(1, ships["pilot_fleets"])
        self.assertEqual([{"key": "dps", "count": 1}], ships["slices"])

    def test_t1_logistics_cruiser_counts_as_logistics(self):
        pilot = self._character(331, "Exequror Pilot", self.user)
        self._attend(pilot, 1, self.groups["exequror"])

        ships = corporation_public_summary(self.corporation)["fleet_ships"]
        self.assertEqual([{"key": "logistics", "count": 1}], ships["slices"])

    def test_kill_buckets_follow_attacker_counts(self):
        hunter = self._character(401, "Hunter", self.user)
        wing = self._character(402, "Wing", self.user)
        self._kill(5001, [hunter.character_id])
        self._kill(5002, [hunter.character_id, 9001, 9002])
        self._kill(
            5003,
            [hunter.character_id, wing.character_id, *range(9100, 9109)],
        )
        self._kill(
            5004,
            [9200, 9201],
            victim_id=hunter.character_id,
            owner=hunter,
        )
        old = self._kill(5005, [hunter.character_id])
        old.killmail_time = timezone.now() - timedelta(days=200)
        old.save(update_fields=["killmail_time"])

        summary = corporation_public_summary(self.corporation)
        kills = summary["kills"]
        self.assertEqual(3, kills["killmails"])
        self.assertEqual(
            [
                {"key": "solo", "count": 1},
                {"key": "small_gang", "count": 1},
                {"key": "fleet", "count": 1},
            ],
            kills["slices"],
        )

    def test_public_info_includes_summary_without_names(self):
        self._status_user("named-pilot", UserCommunityStatus.STATUS_ACTIVE)
        self._character(501, "Named Pilot", self.user)

        response = self.client.get(BASE_URL + "corporations/98726134/info")
        self.assertEqual(200, response.status_code)
        payload = response.json()
        summary = payload["public_summary"]
        self.assertEqual(90, summary["window_days"])
        self.assertEqual(1, summary["community"]["humans"])
        self.assertEqual("active", summary["community"]["slices"][0]["key"])
        self.assertNotIn("Named Pilot", response.content.decode())

    def _status_user(self, username, status):
        if username in ("active-pilot", "named-pilot"):
            user = self.user
        else:
            user = User.objects.create_user(username=username)
        UserCommunityStatus.objects.create(user=user, status=status)
        return user

    def _character(self, character_id, name, user):
        return EveCharacter.objects.create(
            character_id=character_id,
            character_name=name,
            corporation_id=self.corporation.corporation_id,
            user=user,
        )

    def _attend(self, character, instance_id, ship_type_id):
        instance = EveFleetInstance.objects.filter(id=instance_id).first()
        if instance is None:
            fleet = EveFleet.objects.create(
                start_time=timezone.now(),
                type="training",
                created_by=self.user,
            )
            instance = EveFleetInstance.objects.create(
                id=instance_id,
                eve_fleet=fleet,
            )
        return EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=character.character_id,
            character_name=character.character_name,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=ship_type_id,
            ship_name="Hull",
            solar_system_id=1,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )

    def _kill(self, killmail_id, attacker_ids, victim_id=99999, owner=None):
        if owner is None:
            owner = EveCharacter.objects.get(character_id=attacker_ids[0])
        killmail = EveCharacterKillmail.objects.create(
            id=killmail_id,
            killmail_id=killmail_id,
            killmail_hash=f"hash-{killmail_id}",
            killmail_time=timezone.now(),
            solar_system_id=1,
            ship_type_id=self.groups["battleship"],
            victim_character_id=victim_id,
            attackers="[]",
            items="[]",
            character=owner,
        )
        for attacker_id in attacker_ids:
            EveCharacterKillmailAttacker.objects.create(
                killmail=killmail,
                character_id=attacker_id,
            )
        return killmail


def _ship_groups():
    category, _ = EveCategory.objects.get_or_create(
        id=906,
        defaults={"name": "Ship", "published": True},
    )
    names = {
        "battleship": (9061, "Battleship", 6701),
        "logistics": (9062, "Logistics", 6702),
        "interceptor": (9063, "Interceptor", 6703),
        "dreadnought": (9064, "Dreadnought", 6704),
        "industrial": (9065, "Industrial", 6705),
        "capsule": (9066, "Capsule", 670),
        "shuttle": (9067, "Shuttle", 6706),
        "exequror": (9068, "Cruiser", 634),
        "battleship_two": (9061, "Battleship", 6707),
    }
    type_ids = {}
    for key, (group_id, group_name, type_id) in names.items():
        group, _ = EveGroup.objects.get_or_create(
            id=group_id,
            defaults={
                "name": group_name,
                "published": True,
                "eve_category": category,
            },
        )
        EveType.objects.get_or_create(
            id=type_id,
            defaults={
                "name": group_name,
                "published": True,
                "eve_group": group,
            },
        )
        type_ids[key] = type_id
    return type_ids
