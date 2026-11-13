import importlib

import factory
from django.apps import apps
from django.contrib.auth.models import Group, Permission, User
from django.db.models import signals as django_signals
from django.test import TestCase

from help_tickets.models import HelpRequestCategory, HelpTicket
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupRank,
)

migration = importlib.import_module(
    "tribes.migrations.0050_delete_market_tribe_group"
)


MUTED = (
    django_signals.pre_save,
    django_signals.post_save,
    django_signals.pre_delete,
    django_signals.post_delete,
    django_signals.m2m_changed,
)


class DeleteMarketTribeGroupMigrationTestCase(TestCase):
    @factory.django.mute_signals(*MUTED)
    def test_removes_market_and_keeps_hub_access_for_active_members(self):
        supply_auth = Group.objects.create(name="Tribe - Supply")
        tribe = Tribe.objects.create(
            name="Supply", slug="supply", group=supply_auth
        )
        market_auth = Group.objects.create(name="Tribe Group - Market")
        rank_auth = Group.objects.create(name="Tribe Group - Market Lead")
        mining_auth = Group.objects.create(name="Tribe Group - Mining")
        market = TribeGroup.objects.create(
            tribe=tribe,
            name="Market",
            code="supply.market",
            group=market_auth,
        )
        mining = TribeGroup.objects.create(
            tribe=tribe,
            name="Mining",
            code="supply.mining",
            group=mining_auth,
        )
        TribeGroupRank.objects.create(
            tribe_group=market,
            name="Lead",
            code="lead",
            group=rank_auth,
        )
        category = HelpRequestCategory.objects.create(
            title="Market",
            code="supply.market",
            tribe_group=market,
        )
        HelpTicket.objects.create(
            category=category,
            opener_discord_id=1,
            thread_id=99,
            thread_name="market-help",
            body="need a fit",
        )

        only_market = User.objects.create_user(username="only-market")
        only_market.groups.add(market_auth, supply_auth, rank_auth)
        TribeGroupMembership.objects.create(
            user=only_market,
            tribe_group=market,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        also_mining = User.objects.create_user(username="also-mining")
        also_mining.groups.add(market_auth, supply_auth, mining_auth)
        TribeGroupMembership.objects.create(
            user=also_mining,
            tribe_group=market,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        TribeGroupMembership.objects.create(
            user=also_mining,
            tribe_group=mining,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        pending = User.objects.create_user(username="pending")
        pending.groups.add(supply_auth)
        TribeGroupMembership.objects.create(
            user=pending,
            tribe_group=market,
            status=TribeGroupMembership.STATUS_PENDING,
        )

        migration.delete_market_tribe_group(apps, None)

        self.assertFalse(
            TribeGroup.objects.filter(code="supply.market").exists()
        )
        self.assertFalse(Group.objects.filter(pk=market_auth.pk).exists())
        self.assertFalse(Group.objects.filter(pk=rank_auth.pk).exists())
        self.assertTrue(
            TribeGroup.objects.filter(code="supply.mining").exists()
        )
        self.assertTrue(Group.objects.filter(pk=mining_auth.pk).exists())
        self.assertTrue(Group.objects.filter(pk=supply_auth.pk).exists())

        permission = Permission.objects.get(
            content_type__app_label="eveonline",
            codename="change_evelocation",
        )
        only_market.refresh_from_db()
        also_mining.refresh_from_db()
        pending.refresh_from_db()
        self.assertIn(permission, only_market.user_permissions.all())
        self.assertIn(permission, also_mining.user_permissions.all())
        self.assertNotIn(permission, pending.user_permissions.all())

        self.assertFalse(only_market.groups.filter(pk=supply_auth.pk).exists())
        self.assertTrue(also_mining.groups.filter(pk=supply_auth.pk).exists())
        self.assertFalse(pending.groups.filter(pk=supply_auth.pk).exists())

        category.refresh_from_db()
        self.assertIsNone(category.tribe_group_id)
        self.assertFalse(category.is_active)
        self.assertTrue(HelpTicket.objects.filter(thread_id=99).exists())

    def test_noop_when_already_gone(self):
        migration.delete_market_tribe_group(apps, None)
