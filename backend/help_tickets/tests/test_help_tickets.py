"""Tests for help ticket bot API endpoints."""

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from unittest import mock

from discord.models import DiscordUser
from help_tickets.helpers.panel import build_help_ticket_panel_config
from help_tickets.models import (
    HelpRequestCategory,
    HelpTicket,
    HelpTicketPanel,
)
from tribes.models import Tribe, TribeGroup

BASE_URL = "/api/help-tickets"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class HelpTicketPanelConfigTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="bot", password="x")
        self.token = _make_token(self.user)
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.enabled_group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Technology",
            code="pulse.technology",
        )
        self.category = HelpRequestCategory.objects.create(
            title="Contact the technology team",
            code="pulse.technology",
            tribe_group=self.enabled_group,
        )
        HelpRequestCategory.objects.create(
            title="Hidden category",
            code="pulse.hidden",
            is_active=False,
        )

    def test_panel_config_excludes_inactive_categories(self):
        response = self.client.get(
            f"{BASE_URL}/panel-config",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["categories"]), 1)
        self.assertEqual(
            data["categories"][0]["title"], "Contact the technology team"
        )
        self.assertEqual(data["categories"][0]["section"], "Pulse")

    def test_panel_hash_changes_when_title_changes(self):
        config_before = build_help_ticket_panel_config()
        self.category.title = "Updated title"
        self.category.save(update_fields=["title"])
        config_after = build_help_ticket_panel_config()
        self.assertNotEqual(config_before["hash"], config_after["hash"])

    def test_general_category_uses_section_label(self):
        HelpRequestCategory.objects.create(
            title="Contact support",
            code="general.support",
            section="Alliance",
        )
        response = self.client.get(
            f"{BASE_URL}/panel-config",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        sections = {item["section"] for item in response.json()["categories"]}
        self.assertIn("Alliance", sections)


class HelpTicketApiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="bot", password="x")
        self.token = _make_token(self.user)
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Technology",
            code="pulse.technology",
        )
        self.category = HelpRequestCategory.objects.create(
            title="Contact the technology team",
            code="pulse.technology",
            tribe_group=self.group,
        )

    def test_create_help_ticket(self):
        response = self.client.post(
            f"{BASE_URL}/",
            data={
                "category_id": self.category.pk,
                "opener_discord_id": 123456789,
                "thread_id": 987654321,
                "thread_name": "pulse.technology-opener",
                "body": "Need help with login",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        ticket = HelpTicket.objects.get(pk=response.json()["id"])
        self.assertEqual(ticket.status, HelpTicket.STATUS_OPEN)
        self.assertIsNotNone(ticket.opened_at)

    def test_create_rejects_inactive_category(self):
        self.category.is_active = False
        self.category.save(update_fields=["is_active"])
        response = self.client.post(
            f"{BASE_URL}/",
            data={
                "category_id": self.category.pk,
                "opener_discord_id": 123456789,
                "thread_id": 987654322,
                "thread_name": "pulse.technology-opener2",
                "body": "Need help",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)

    def test_close_help_ticket(self):
        ticket = HelpTicket.objects.create(
            category=self.category,
            opener_discord_id=123456789,
            thread_id=111,
            thread_name="test-thread",
            body="Help",
        )
        with mock.patch(
            "help_tickets.router.discord.close_thread",
        ) as close_thread:
            response = self.client.patch(
                f"{BASE_URL}/{ticket.pk}/close/",
                data={
                    "closed_by_discord_id": 999888777,
                    "close_reason": "Resolved",
                },
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(response.status_code, 200)
        close_thread.assert_called_once_with(channel_id=111)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, HelpTicket.STATUS_CLOSED)
        self.assertIsNotNone(ticket.closed_at)
        self.assertEqual(ticket.close_reason, "Resolved")

    def test_close_help_ticket_discord_failure_leaves_ticket_open(self):
        ticket = HelpTicket.objects.create(
            category=self.category,
            opener_discord_id=123456789,
            thread_id=112,
            thread_name="test-thread-2",
            body="Help",
        )
        with mock.patch(
            "help_tickets.router.discord.close_thread",
            side_effect=RuntimeError("discord down"),
        ):
            response = self.client.patch(
                f"{BASE_URL}/{ticket.pk}/close/",
                data={
                    "closed_by_discord_id": 999888777,
                    "close_reason": "Resolved",
                },
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(response.status_code, 502)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, HelpTicket.STATUS_OPEN)

    def test_panel_state_update(self):
        response = self.client.put(
            f"{BASE_URL}/panel-state",
            data={
                "channel_id": 1183401618943791186,
                "message_id": 555,
                "content_hash": "abc123",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        panel = HelpTicketPanel.get_solo()
        self.assertEqual(panel.message_id, 555)
        self.assertEqual(panel.content_hash, "abc123")

    def test_list_open_help_tickets(self):
        HelpTicket.objects.create(
            category=self.category,
            opener_discord_id=1,
            thread_id=100,
            thread_name="open-thread",
            body="Open",
            status=HelpTicket.STATUS_OPEN,
        )
        HelpTicket.objects.create(
            category=self.category,
            opener_discord_id=2,
            thread_id=101,
            thread_name="closed-thread",
            body="Closed",
            status=HelpTicket.STATUS_CLOSED,
        )
        response = self.client.get(
            f"{BASE_URL}/open",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["tickets"]), 1)
        self.assertEqual(data["tickets"][0]["thread_id"], 100)

    def test_create_links_opener_when_discord_user_exists(self):
        opener = User.objects.create_user(username="opener", password="x")
        DiscordUser.objects.create(
            id=123456789,
            discord_tag="opener#0",
            avatar="",
            user=opener,
        )
        response = self.client.post(
            f"{BASE_URL}/",
            data={
                "category_id": self.category.pk,
                "opener_discord_id": 123456789,
                "thread_id": 987654323,
                "thread_name": "pulse.technology-opener3",
                "body": "Need help",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        ticket = HelpTicket.objects.get(pk=response.json()["id"])
        self.assertEqual(ticket.opener_id, opener.pk)

    def test_panel_config_includes_assignee_mentions(self):
        assignee = User.objects.create_user(username="lead", password="x")
        DiscordUser.objects.create(
            id=555444333,
            discord_tag="lead#0",
            avatar="",
            user=assignee,
        )
        category = HelpRequestCategory.objects.create(
            title="General help",
            code="general.help",
            section="Alliance",
        )
        category.assignees.add(assignee)
        response = self.client.get(
            f"{BASE_URL}/panel-config",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        general = next(
            item
            for item in response.json()["categories"]
            if item["id"] == category.pk
        )
        self.assertEqual(general["mention_discord_ids"], [555444333])
