"""Tests for tribe catalog report bindings and query modules."""

import json
from datetime import date, timedelta
from pathlib import Path

import factory
from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.utils import timezone

from discord.models import DiscordRole
from discord.signals import (
    group_post_save,
    resolve_existing_discord_role_from_server,
    user_group_changed,
)

from app.test import TestCase
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
)
from eveonline.models.characters import EveCharacterMiningEntry, EvePlayer
from eveuniverse.models import EveCategory, EveGroup, EveMarketPrice, EveType
from fleets.models import EveFleet
from industry.models import (
    IndustryOrder,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
)
from tribes.helpers.group_code import make_tribe_group_code
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupRequirement,
    TribeGroupRequirementAssetType,
)
from tribes.reports.period import parse_period
from tribes.reports.queries.capitals import run_capitals_report
from tribes.reports.queries.fleet_commanders import run_fleet_commanders_report
from tribes.reports.queries.industry_orders import run_industry_orders_report
from tribes.reports.queries.mining import run_mining_report
from tribes.reports.registry import REPORT_BINDINGS, get_binding
from tribes.reports.runner import ReportError, run_group_report
from tribes.reports.types import ReportScope, ReportView


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


def _ensure_eve_type(type_id: int, name: str, volume: float = 0.1) -> EveType:
    now = timezone.now()
    category, _ = EveCategory.objects.get_or_create(
        id=99001,
        defaults={
            "name": "Test Category",
            "last_updated": now,
            "published": True,
        },
    )
    group, _ = EveGroup.objects.get_or_create(
        id=99001,
        defaults={
            "name": "Test Group",
            "last_updated": now,
            "published": True,
            "eve_category": category,
        },
    )
    eve_type, _ = EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": name,
            "last_updated": now,
            "published": True,
            "eve_group": group,
            "volume": volume,
        },
    )
    return eve_type


def _make_group(tribe, name: str) -> TribeGroup:
    return TribeGroup.objects.create(
        tribe=tribe,
        name=name,
        code=make_tribe_group_code(tribe.slug, name),
    )


class ReportRegistryTestCase(TestCase):
    def test_fixture_groups_have_bindings(self):
        fixture_path = (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "data"
            / "06_tribes.json"
        )
        data = json.loads(fixture_path.read_text())
        groups = [
            obj
            for obj in data
            if obj["model"] == "tribes.tribegroup"
            and obj["fields"].get("is_active", True)
        ]
        self.assertGreater(len(groups), 0)
        for obj in groups:
            code = obj["fields"].get("code")
            self.assertTrue(code, f"Group pk={obj['pk']} missing code")
            binding = get_binding(code)
            self.assertIsNotNone(
                binding,
                f"No report binding for fixture group code {code!r}",
            )

    def test_manual_pulse_groups(self):
        for code in (
            "pulse.technology",
            "pulse.readiness",
            "market.contracts",
        ):
            binding = get_binding(code)
            self.assertTrue(binding.manual)

    def test_automated_bindings_have_runners(self):
        for code, binding in REPORT_BINDINGS.items():
            if binding.manual:
                continue
            for view, spec in binding.views.items():
                self.assertIn(
                    spec.query_key,
                    (
                        "mining_by_user",
                        "pi_by_user",
                        "industry_orders_by_user",
                        "freight_program",
                        "fleet_commanders",
                        "capitals_activity",
                    ),
                    f"{code} view {view} unknown query {spec.query_key}",
                )


class MiningReportTestCase(TestCase):
    @factory.django.mute_signals(
        django_signals.pre_save, django_signals.post_save
    )
    def setUp(self):
        super().setUp()
        self.tribe = Tribe.objects.create(name="Industry", slug="industry")
        self.group = _make_group(self.tribe, "Mining")
        self.user = User.objects.create_user(username="miner")
        self.character = EveCharacter.objects.create(
            character_id=7001,
            character_name="Test Miner",
            user=self.user,
        )
        EvePlayer.objects.create(
            user=self.user, primary_character=self.character
        )
        membership = TribeGroupMembership.objects.create(
            tribe_group=self.group,
            user=self.user,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        TribeGroupMembershipCharacter.objects.create(
            membership=membership,
            character=self.character,
        )
        ore = _ensure_eve_type(1228, "Scordite", volume=0.15)
        EveMarketPrice.objects.create(eve_type=ore, average_price=100.0)
        today = timezone.now().date()
        EveCharacterMiningEntry.objects.create(
            character=self.character,
            eve_type=ore,
            date=today - timedelta(days=3),
            quantity=1000,
            solar_system_id=30001,
        )

    def test_roster_mining_totals(self):
        period = parse_period("30d")
        rows, totals, columns = run_mining_report(
            self.group, period, ReportScope.ROSTER, {}
        )
        self.assertIn("primary_character_name", columns)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["volume_m3"], 150.0)
        self.assertAlmostEqual(rows[0]["isk_ore_market_estimate"], 100000.0)
        self.assertAlmostEqual(totals["total_volume_m3"], 150.0)

    def test_mining_scope_override_via_runner(self):
        outsider = User.objects.create_user(username="outsider")
        outsider_char = EveCharacter.objects.create(
            character_id=7002,
            character_name="Outsider Miner",
            user=outsider,
        )
        ore = EveType.objects.get(id=1228)
        today = timezone.now().date()
        EveCharacterMiningEntry.objects.create(
            character=outsider_char,
            eve_type=ore,
            date=today - timedelta(days=2),
            quantity=2000,
            solar_system_id=30001,
        )

        period = parse_period("30d")
        roster_result = run_group_report(
            self.group,
            view=ReportView.TOWN_HALL.value,
            period=period.label,
            scope="roster",
        )
        alliance_result = run_group_report(
            self.group,
            view=ReportView.TOWN_HALL.value,
            period=period.label,
            scope="alliance",
        )
        self.assertEqual(roster_result.scope, "roster")
        self.assertEqual(alliance_result.scope, "alliance")
        self.assertAlmostEqual(roster_result.totals["total_volume_m3"], 150.0)
        self.assertAlmostEqual(
            alliance_result.totals["total_volume_m3"], 450.0
        )


class FleetCommandersReportTestCase(TestCase):
    @factory.django.mute_signals(
        django_signals.pre_save, django_signals.post_save
    )
    def setUp(self):
        super().setUp()
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Fleet Commanders",
            code="pulse.fleet-commanders",
        )
        self.fc = User.objects.create_user(username="fc")
        membership = TribeGroupMembership.objects.create(
            tribe_group=self.group,
            user=self.fc,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        char = EveCharacter.objects.create(
            character_id=8001,
            character_name="FC Pilot",
            user=self.fc,
        )
        TribeGroupMembershipCharacter.objects.create(
            membership=membership,
            character=char,
        )
        EvePlayer.objects.create(user=self.fc, primary_character=char)
        now = timezone.now()
        EveFleet.objects.create(
            type="strategic",
            start_time=now - timedelta(days=2),
            created_by=self.fc,
            status="complete",
        )
        EveFleet.objects.create(
            type="training",
            start_time=now - timedelta(days=1),
            created_by=self.fc,
            status="cancelled",
        )

    def test_roster_fc_count_excludes_cancelled(self):
        period = parse_period("30d")
        rows, totals, columns = run_fleet_commanders_report(
            self.group, period, ReportScope.ROSTER, {}
        )
        self.assertIn("fleet_count", columns)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["fleet_count"], 1)
        self.assertEqual(totals["total_fleets"], 1)


class IndustryOrdersReportTestCase(TestCase):
    @factory.django.mute_signals(
        django_signals.pre_save, django_signals.post_save
    )
    def setUp(self):
        super().setUp()
        self.tribe = Tribe.objects.create(name="Industry", slug="industry")
        self.group = _make_group(self.tribe, "Subcapital Production")
        self.builder = User.objects.create_user(username="builder")
        self.character = EveCharacter.objects.create(
            character_id=9001,
            character_name="Builder",
            user=self.builder,
        )
        membership = TribeGroupMembership.objects.create(
            tribe_group=self.group,
            user=self.builder,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        TribeGroupMembershipCharacter.objects.create(
            membership=membership,
            character=self.character,
        )
        product = _ensure_eve_type(111, "Product")
        order = IndustryOrder.objects.create(
            needed_by=date.today() + timedelta(days=7),
            public_short_code="ABC",
            character=self.character,
        )
        order.tribe_groups.add(self.group)
        item = IndustryOrderItem.objects.create(
            order=order,
            eve_type=product,
            quantity=10,
            target_estimated_margin=100,
        )
        delivered_at = timezone.now() - timedelta(days=2)
        IndustryOrderItemAssignment.objects.create(
            order_item=item,
            character=self.character,
            quantity=5,
            target_estimated_margin=100,
            delivered_at=delivered_at,
        )

    def test_delivered_units_in_period(self):
        period = parse_period("30d")
        rows, totals, columns = run_industry_orders_report(
            self.group, period, ReportScope.ROSTER, {}
        )
        self.assertIn("delivered_units", columns)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["delivered_units"], 5)
        self.assertEqual(totals["delivered_units"], 5)


class CapitalsReportTestCase(TestCase):
    @factory.django.mute_signals(
        django_signals.pre_save, django_signals.post_save
    )
    def setUp(self):
        super().setUp()
        self.dread_type_id = 23773
        _ensure_eve_type(self.dread_type_id, "Naglfar")
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Dreads",
            code="capitals.dreads",
        )
        requirement = TribeGroupRequirement.objects.create(
            tribe_group=self.group,
        )
        TribeGroupRequirementAssetType.objects.create(
            requirement=requirement,
            eve_type_id=self.dread_type_id,
        )

        self.killer_user = User.objects.create_user(username="killer")
        self.loser_user = User.objects.create_user(username="loser")
        self.killer_char = EveCharacter.objects.create(
            character_id=11001,
            character_name="Killer",
            user=self.killer_user,
        )
        self.loser_char = EveCharacter.objects.create(
            character_id=11002,
            character_name="Loser",
            user=self.loser_user,
        )
        for user, char in (
            (self.killer_user, self.killer_char),
            (self.loser_user, self.loser_char),
        ):
            membership = TribeGroupMembership.objects.create(
                tribe_group=self.group,
                user=user,
                status=TribeGroupMembership.STATUS_ACTIVE,
            )
            TribeGroupMembershipCharacter.objects.create(
                membership=membership,
                character=char,
            )
            EvePlayer.objects.create(
                user=user,
                primary_character=char,
                nickname=f"player-{user.username}",
            )

        kill_time = timezone.now() - timedelta(days=1)
        killmail = EveCharacterKillmail.objects.create(
            id=100001,
            killmail_id=900101,
            killmail_hash="kill",
            killmail_time=kill_time,
            solar_system_id=30001,
            ship_type_id=587,
            victim_character_id=99999,
            victim_corporation_id=1,
            victim_alliance_id=1,
            victim_faction_id=None,
            attackers="[]",
            items="[]",
            character=self.killer_char,
        )
        EveCharacterKillmailAttacker.objects.create(
            killmail=killmail,
            character_id=self.killer_char.character_id,
            ship_type_id=self.dread_type_id,
        )

        EveCharacterKillmail.objects.create(
            id=100002,
            killmail_id=900102,
            killmail_hash="loss",
            killmail_time=kill_time,
            solar_system_id=30001,
            ship_type_id=self.dread_type_id,
            victim_character_id=self.loser_char.character_id,
            victim_corporation_id=1,
            victim_alliance_id=1,
            victim_faction_id=None,
            attackers="[]",
            items="[]",
            character=self.loser_char,
        )

    def test_counts_kills_and_victim_losses_separately(self):
        period = parse_period("30d")
        rows, totals, columns = run_capitals_report(
            self.group, period, ReportScope.ROSTER, {}
        )
        self.assertIn("loss_count", columns)
        self.assertEqual(totals["total_kills"], 1)
        self.assertEqual(totals["total_losses"], 1)

        by_name = {r["primary_character_name"]: r for r in rows}
        self.assertEqual(by_name["Killer"]["kill_count"], 1)
        self.assertEqual(by_name["Killer"]["loss_count"], 0)
        self.assertEqual(by_name["Loser"]["kill_count"], 0)
        self.assertEqual(by_name["Loser"]["loss_count"], 1)

    def test_town_hall_top_n_limits_rows(self):
        result = run_group_report(
            self.group,
            view=ReportView.TOWN_HALL.value,
            period="30d",
            scope="roster",
        )
        self.assertLessEqual(len(result.rows), 5)
        self.assertEqual(result.totals["total_kills"], 1)


class ReportRunnerTestCase(TestCase):
    @factory.django.mute_signals(
        django_signals.pre_save, django_signals.post_save
    )
    def setUp(self):
        super().setUp()
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Readiness",
            code="pulse.readiness",
        )

    def test_manual_binding(self):
        result = run_group_report(
            self.group, view=ReportView.TOWN_HALL.value, period="30d"
        )
        self.assertTrue(result.manual)

    def test_unknown_group_code_raises(self):
        self.group.code = "unknown.group"
        self.group.save(update_fields=["code"])
        with self.assertRaises(ReportError):
            run_group_report(self.group)

    def test_unknown_database_raises(self):
        with self.assertRaises(ReportError) as ctx:
            run_group_report(
                self.group,
                database="does_not_exist",
            )
        self.assertIn("Unknown database alias", str(ctx.exception))

    def test_invalid_scope_override_raises(self):
        mining_group = TribeGroup.objects.create(
            tribe=Tribe.objects.create(name="Industry", slug="industry2"),
            name="Mining",
            code="industry.mining",
        )
        with self.assertRaises(ReportError) as ctx:
            run_group_report(
                mining_group,
                scope="program",
            )
        self.assertIn("roster or alliance", str(ctx.exception))
