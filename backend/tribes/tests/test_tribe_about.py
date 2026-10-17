"""Tests for the tribe About page rollup, cache and endpoint."""

from datetime import timedelta
from unittest.mock import patch

import factory
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import signals as django_signals
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import make_token
from discord.models import DiscordRole
from discord.signals import (
    group_post_save,
    resolve_existing_discord_role_from_server,
    user_group_changed,
)
from eveonline.models import (
    EveCharacter,
    EveCharacterAsset,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
)
from eveonline.models.characters import EvePlayer
from eveuniverse.models import EveCategory, EveGroup, EveType
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
)
from tribes.helpers import about as about_helpers
from tribes.helpers.about import (
    capitals_block,
    compute_tribe_about,
    tribe_about,
)
from tribes.helpers.growth import tribe_membership_growth
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipHistory,
    TribeGroupRequirement,
    TribeGroupRequirementAssetType,
)

BASE_URL = "/api/tribes"
REVELATION = 19720
MOROS = 19724


def setUpModule():
    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )
    django_signals.post_save.disconnect(
        group_post_save, sender=Group, dispatch_uid="group_post_save"
    )
    django_signals.pre_save.disconnect(
        resolve_existing_discord_role_from_server,
        sender=DiscordRole,
        dispatch_uid="resolve_existing_discord_role_from_server",
    )


def _grant_alliance_perm(user: User) -> None:
    content_type = ContentType.objects.get(
        app_label="eveonline", model="evecharactertag"
    )
    perm, _ = Permission.objects.get_or_create(
        codename="add_evecharactertag",
        content_type=content_type,
        defaults={"name": "Can add eve character tag"},
    )
    user.user_permissions.add(perm)


def _ensure_type(type_id: int, name: str, group_name: str) -> None:
    now = timezone.now()
    category, _ = EveCategory.objects.get_or_create(
        id=6, defaults={"name": "Ship", "last_updated": now, "published": True}
    )
    group, _ = EveGroup.objects.get_or_create(
        id=485,
        defaults={
            "name": group_name,
            "last_updated": now,
            "published": True,
            "eve_category": category,
        },
    )
    EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": name,
            "last_updated": now,
            "published": True,
            "eve_group": group,
        },
    )


def _join(group, user, character):
    membership = TribeGroupMembership.objects.create(
        tribe_group=group,
        user=user,
        status=TribeGroupMembership.STATUS_ACTIVE,
        approved_at=timezone.now() - timedelta(days=60),
    )
    TribeGroupMembershipCharacter.objects.create(
        membership=membership, character=character
    )
    return membership


class CapitalsAboutTestCase(TestCase):
    @factory.django.mute_signals(
        django_signals.pre_save, django_signals.post_save
    )
    def setUp(self):
        super().setUp()
        cache.clear()
        _ensure_type(REVELATION, "Revelation", "Dreadnought")
        _ensure_type(MOROS, "Moros", "Dreadnought")
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.dreads = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads", code="capitals.dreads"
        )
        requirement = TribeGroupRequirement.objects.create(
            tribe_group=self.dreads
        )
        TribeGroupRequirementAssetType.objects.create(
            requirement=requirement, eve_type_id=REVELATION
        )

        self.users = []
        self.chars = []
        for index in range(2):
            user = User.objects.create_user(username=f"dread{index}")
            char = EveCharacter.objects.create(
                character_id=21000 + index,
                character_name=f"Dread Pilot {index}",
                user=user,
            )
            EvePlayer.objects.create(
                user=user, primary_character=char, nickname=user.username
            )
            _join(self.dreads, user, char)
            EveCharacterAsset.objects.create(
                type_id=REVELATION,
                type_name="Revelation",
                location_id=1,
                location_name="Amamake",
                character=char,
            )
            self.users.append(user)
            self.chars.append(char)

        kill_time = timezone.now() - timedelta(days=3)
        # Both pilots are on the same enemy dread: one kill, not two.
        for index, char in enumerate(self.chars):
            killmail = EveCharacterKillmail.objects.create(
                id=500 + index,
                killmail_id=777001,
                killmail_hash="hash",
                killmail_time=kill_time,
                solar_system_id=30002537,
                ship_type_id=MOROS,
                victim_character_id=99,
                attackers="[]",
                items="[]",
                character=char,
            )
            EveCharacterKillmailAttacker.objects.create(
                killmail=killmail,
                character_id=char.character_id,
                ship_type_id=REVELATION,
            )

        fleet = EveFleet.objects.create(
            audience=EveFleetAudience.objects.create(name="Capitals"),
            start_time=kill_time,
            type="strategic",
            description="Dread drop",
        )
        instance = EveFleetInstance.objects.create(
            id=8801, eve_fleet=fleet, start_time=kill_time
        )
        for char in self.chars:
            EveFleetInstanceMember.objects.create(
                eve_fleet_instance=instance,
                character_id=char.character_id,
                character_name=char.character_name,
                role="squad_member",
                role_name="Squad Member",
                ship_type_id=REVELATION,
                ship_name="Revelation",
                solar_system_id=30002537,
                solar_system_name="Amamake",
                squad_id=1,
                wing_id=1,
            )

    def test_capital_line_counts_hulls_kills_and_turnout(self):
        block = capitals_block([self.dreads])

        self.assertEqual(block["hangar"][0]["total"], 2)
        self.assertEqual(block["hangar"][0]["hulls"][0]["name"], "Revelation")
        self.assertEqual(block["year_kills"], 1)
        self.assertEqual(block["all_time_kills"], 1)
        self.assertEqual(block["capital_kills_year"], 1)
        self.assertEqual(
            block["recent_capital_kills"][0]["ship_name"], "Moros"
        )
        self.assertEqual(block["fleets_year"], 1)
        self.assertEqual(block["record_turnout"]["pilots"], 2)
        self.assertEqual(block["record_turnout"]["systems"], ["Amamake"])
        self.assertEqual(sum(block["hours"]), 1)
        self.assertEqual(len(block["kills_by_month"]), 12)

    def test_compute_includes_people_groups_and_capitals(self):
        about = compute_tribe_about(self.tribe)

        self.assertEqual(about["people"], 2)
        self.assertEqual(about["multi_group_people"], 0)
        self.assertEqual(len(about["groups"]), 1)
        dreads = about["groups"][0]
        self.assertEqual(dreads["member_count"], 2)
        self.assertEqual(dreads["totals"]["total_kills"], 2)
        self.assertEqual(len(dreads["top_pilots"]), 2)
        self.assertIsNotNone(about["capitals"])
        self.assertIsNone(about["supply"])


class TribeGrowthTestCase(TestCase):
    def test_person_in_two_groups_counts_once(self):
        tribe = Tribe.objects.create(name="Supply", slug="supply")
        mining = TribeGroup.objects.create(
            tribe=tribe, name="Mining", code="supply.mining"
        )
        market = TribeGroup.objects.create(
            tribe=tribe, name="Market", code="supply.market"
        )
        user = User.objects.create_user(username="both")
        past = timezone.now() - timedelta(days=90)
        for group in (mining, market):
            membership = TribeGroupMembership.objects.create(
                tribe_group=group,
                user=user,
                status=TribeGroupMembership.STATUS_ACTIVE,
                approved_at=past,
            )
            # Active since three months ago, so it covers completed months.
            TribeGroupMembershipHistory.objects.filter(
                membership=membership
            ).delete()
            TribeGroupMembershipHistory.objects.create(
                membership=membership,
                from_status=TribeGroupMembership.STATUS_PENDING,
                to_status=TribeGroupMembership.STATUS_ACTIVE,
                changed_at=past,
                reason="approved",
            )

        growth = tribe_membership_growth(tribe)

        self.assertEqual(growth["counts"][-1], 1)


class TribeAboutCacheTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")

    def test_miss_queues_one_refresh(self):
        with patch.object(about_helpers, "_queue_refresh") as queue:
            self.assertIsNone(tribe_about(self.tribe.pk))
            self.assertIsNone(tribe_about(self.tribe.pk))
        queue.assert_called_once_with(self.tribe.pk)

    def test_eager_refresh_fills_the_cache(self):
        about = tribe_about(self.tribe.pk)

        self.assertIsNotNone(about)
        self.assertEqual(about["slug"], "pulse")


class TribeAboutEndpointTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.open_group = TribeGroup.objects.create(
            tribe=self.tribe, name="Technology", code="pulse.technology"
        )
        self.hidden_group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Fishermen",
            code="pulse.fishermen",
            roster_hidden=True,
        )
        self.alliance = User.objects.create_user(username="ally")
        _grant_alliance_perm(self.alliance)

    def _payload(self):
        pilot = {"character_id": 1, "character_name": "Pilot", "value": 3}
        return {
            "tribe_id": self.tribe.pk,
            "slug": "pulse",
            "generated_at": timezone.now().isoformat(),
            "people": 2,
            "multi_group_people": 0,
            "growth": {"months": [], "counts": []},
            "corporations": [],
            "corporation_count": 0,
            "groups": [
                {
                    "id": group.pk,
                    "code": group.code,
                    "name": group.name,
                    "member_count": 1,
                    "manual": False,
                    "totals": {"tickets_resolved": 3},
                    "highlights": {},
                    "top_pilots": [pilot],
                }
                for group in (self.open_group, self.hidden_group)
            ],
            "capitals": None,
            "supply": None,
        }

    def _get(self, user=None):
        headers = {}
        if user:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {make_token(user)}"
        with patch(
            "tribes.endpoints.tribes.get_tribe_about.tribe_about",
            return_value=self._payload(),
        ):
            response = self.client.get(
                f"{BASE_URL}/{self.tribe.pk}/about", **headers
            )
        self.assertEqual(response.status_code, 200)
        return {g["code"]: g for g in response.json()["groups"]}

    def test_guest_gets_totals_without_names(self):
        groups = self._get()

        self.assertEqual(groups["pulse.technology"]["top_pilots"], [])
        self.assertEqual(
            groups["pulse.technology"]["totals"]["tickets_resolved"], 3
        )

    def test_alliance_member_sees_names_except_hidden_rosters(self):
        groups = self._get(self.alliance)

        self.assertEqual(
            groups["pulse.technology"]["top_pilots"][0]["character_name"],
            "Pilot",
        )
        self.assertEqual(groups["pulse.fishermen"]["top_pilots"], [])

    def test_not_ready_until_cached(self):
        with patch(
            "tribes.endpoints.tribes.get_tribe_about.tribe_about",
            return_value=None,
        ):
            response = self.client.get(f"{BASE_URL}/{self.tribe.pk}/about")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ready"])

    def test_unknown_tribe_is_404(self):
        response = self.client.get(f"{BASE_URL}/999999/about")

        self.assertEqual(response.status_code, 404)
