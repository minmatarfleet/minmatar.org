"""Tests for Industry+Market → Supply merge helpers."""

from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import TestCase
from django.utils import timezone

from discord.models import DiscordRole
from discord.signals import (
    group_post_save,
    resolve_existing_discord_role_from_server,
    user_group_changed,
)
from tribes.helpers.merge_supply_tribe import run_merge_supply_tribe
from tribes.models import Tribe, TribeGroup, TribeGroupMembership


def setUpModule():
    """Disconnect Discord signals that hit the live API."""
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


class MergeSupplyTribeTestCase(TestCase):
    def setUp(self):
        self.industry_auth = Group.objects.create(name="Tribe - Industry")
        self.market_auth = Group.objects.create(name="Tribe - Market")
        self.contracts_auth = Group.objects.create(
            name="Tribe Group - Contracts"
        )
        self.orders_auth = Group.objects.create(
            name="Tribe Group - Market Orders"
        )

        self.industry = Tribe.objects.create(
            name="Industry",
            slug="industry",
            group=self.industry_auth,
            is_active=True,
        )
        self.market_tribe = Tribe.objects.create(
            name="Market",
            slug="market",
            group=self.market_auth,
            is_active=True,
        )

        self.mining = TribeGroup.objects.create(
            tribe=self.industry,
            name="Mining",
            code="industry.mining",
            is_active=True,
        )
        self.contracts = TribeGroup.objects.create(
            tribe=self.market_tribe,
            name="Contracts",
            code="market.contracts",
            group=self.contracts_auth,
            is_active=True,
        )
        self.orders = TribeGroup.objects.create(
            tribe=self.market_tribe,
            name="Market Orders",
            code="market.market-orders",
            group=self.orders_auth,
            is_active=True,
        )
        self.freighters = TribeGroup.objects.create(
            tribe=self.market_tribe,
            name="Freighters",
            code="market.freighters",
            is_active=True,
        )

        self.user_market_only = User.objects.create_user(username="mkt_only")
        self.user_market_only.groups.add(self.market_auth, self.orders_auth)

        self.user_both = User.objects.create_user(username="both_groups")
        self.user_both.groups.add(
            self.industry_auth, self.market_auth, self.contracts_auth
        )

        TribeGroupMembership.objects.create(
            user=self.user_market_only,
            tribe_group=self.orders,
            status=TribeGroupMembership.STATUS_ACTIVE,
            approved_at=timezone.now(),
        )
        TribeGroupMembership.objects.create(
            user=self.user_both,
            tribe_group=self.contracts,
            status=TribeGroupMembership.STATUS_ACTIVE,
            approved_at=timezone.now(),
        )
        TribeGroupMembership.objects.create(
            user=self.user_both,
            tribe_group=self.orders,
            status=TribeGroupMembership.STATUS_PENDING,
        )

    def test_dry_run_writes_nothing(self):
        log = run_merge_supply_tribe(apply=False)
        self.assertTrue(any("DRY-RUN" in line for line in log.lines))
        self.industry.refresh_from_db()
        self.assertEqual(self.industry.slug, "industry")
        self.assertTrue(Group.objects.filter(name="Tribe - Industry").exists())
        self.assertFalse(Group.objects.filter(name="Tribe - Supply").exists())

    def test_apply_merges_catalog_and_auth(self):
        with self.settings(DISCORD_BOT_TOKEN="test", DISCORD_GUILD_ID="1"):
            with patch(
                "tribes.helpers.merge_supply_tribe.DiscordClient"
            ) as client_cls:
                client_cls.return_value.edit_role.return_value = None
                log = run_merge_supply_tribe(apply=True)

        self.assertTrue(any("APPLY" in line for line in log.lines))

        supply = Tribe.objects.get(slug="supply")
        self.assertEqual(supply.name, "Supply")
        self.assertTrue(supply.is_active)
        self.assertEqual(supply.group.name, "Tribe - Supply")

        market_tribe = Tribe.objects.get(slug="market")
        self.assertFalse(market_tribe.is_active)

        market_group = TribeGroup.objects.get(code="supply.market")
        self.assertEqual(market_group.name, "Market")
        self.assertEqual(market_group.tribe_id, supply.pk)
        self.assertTrue(market_group.is_active)
        self.assertEqual(market_group.group.name, "Tribe Group - Market")

        freighters = TribeGroup.objects.get(code="supply.freighters")
        self.assertEqual(freighters.tribe_id, supply.pk)

        mining = TribeGroup.objects.get(code="supply.mining")
        self.assertEqual(mining.tribe_id, supply.pk)

        orders = TribeGroup.objects.get(code="market.market-orders")
        self.assertFalse(orders.is_active)

        self.user_market_only.refresh_from_db()
        self.assertTrue(
            self.user_market_only.groups.filter(name="Tribe - Supply").exists()
        )
        self.assertFalse(
            self.user_market_only.groups.filter(name="Tribe - Market").exists()
        )
        self.assertTrue(
            self.user_market_only.groups.filter(
                name="Tribe Group - Market"
            ).exists()
        )
        self.assertFalse(
            self.user_market_only.groups.filter(
                name="Tribe Group - Market Orders"
            ).exists()
        )

        # Orders-only user moved onto supply.market
        m = TribeGroupMembership.objects.get(
            user=self.user_market_only, tribe_group=market_group
        )
        self.assertEqual(m.status, TribeGroupMembership.STATUS_ACTIVE)

        # Dual membership: survivor kept active; orders retired
        both_survivor = TribeGroupMembership.objects.get(
            user=self.user_both, tribe_group=market_group
        )
        self.assertEqual(
            both_survivor.status, TribeGroupMembership.STATUS_ACTIVE
        )
        both_orders = TribeGroupMembership.objects.get(
            user=self.user_both, tribe_group=orders
        )
        self.assertEqual(
            both_orders.status, TribeGroupMembership.STATUS_INACTIVE
        )

    def test_apply_idempotent(self):
        with patch(
            "tribes.helpers.merge_supply_tribe.DiscordClient"
        ) as client_cls:
            client_cls.return_value.edit_role.return_value = None
            run_merge_supply_tribe(apply=True)
            run_merge_supply_tribe(apply=True)

        self.assertEqual(Tribe.objects.filter(slug="supply").count(), 1)
        self.assertEqual(
            TribeGroup.objects.filter(code="supply.market").count(), 1
        )
