"""Tests for NPSI calendar ingest."""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import jwt
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.utils import timezone

from app.test import TestCase
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EveCorporation
from eveonline.helpers.characters import set_primary_character
from fleets.helpers.npsi_description import sanitize_npsi_description
from fleets.helpers.npsi_ingest import (
    event_fingerprint,
    poll_npsi_sources,
    upsert_feed_item,
)
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    NpsiEventSource,
    NpsiExternalEvent,
)
from fleets.tests import disconnect_fleet_signals, setup_fleet_reference_data

UNALIGNED_HTML = (
    "Roaming through nullsec and taking fights outnumbered!"
    "<br><br>Doctrine:\xa0"
    '<a href="https://eveworkbench.com/fleet/598638a9-bd3a-4b6c-57bb-08de7d0f3e96"'
    ' target="_blank"><u><u><u>'
    "https://eveworkbench.com/fleet/598638a9-bd3a-4b6c-57bb-08de7d0f3e96"
    "</u></u></u></a><br>Discord:\xa0"
    '<a href="https://discord.gg/26QbDN357A" target="_blank">'
    "<u><u>https://discord.gg/26QbDN357A</u></u></a><br>"
    "In game channel: 'Unaligned NPSI'<br>Formup: Jita<br><br>"
    "**FC: Vex Drake**"
)


class NpsiDescriptionTestCase(TestCase):
    def test_unaligned_html_is_readable(self):
        text = sanitize_npsi_description(UNALIGNED_HTML)
        self.assertIn(
            "Roaming through nullsec and taking fights outnumbered!", text
        )
        self.assertIn(
            "Doctrine: https://eveworkbench.com/fleet/598638a9-bd3a-4b6c-57bb-08de7d0f3e96",
            text,
        )
        self.assertIn("Discord: https://discord.gg/26QbDN357A", text)
        self.assertIn("In game channel: 'Unaligned NPSI'", text)
        self.assertIn("Formup: Jita", text)
        self.assertIn("FC: Vex Drake", text)
        self.assertNotIn("<", text)
        self.assertNotIn("**", text)


class NpsiIngestTestCase(TestCase):
    def setUp(self):
        super().setUp()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.audience = EveFleetAudience.objects.get(name="Test Audience")
        self.source, _ = NpsiEventSource.objects.update_or_create(
            name="Unaligned",
            defaults={
                "feed_url": "https://example.test/events",
                "fc_character_name": "Vex Drake",
                "default_audience": self.audience,
                "default_type": "non_strategic",
                "enabled": True,
            },
        )
        corp = EveCorporation.objects.create(
            corporation_id=1, name="Test Corp"
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_evefleet")
        )
        char = EveCharacter.objects.create(
            character_id=111,
            character_name="Vex Drake",
            user=self.user,
            corporation_id=corp.corporation_id,
        )
        set_primary_character(self.user, char)
        DiscordUser.objects.create(id=4242, discord_tag="vex", user=self.user)

    def _item(self, **overrides):
        start = timezone.now() + timedelta(days=6)
        data = {
            "summary": "Roaming Navies",
            "description": UNALIGNED_HTML,
            "location": "Jita",
            "start": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "end": (start + timedelta(hours=3)).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            ),
            "allDay": False,
            "character_name": "Vex Drake",
        }
        data.update(overrides)
        return data

    @patch("fleets.helpers.npsi_ingest.DiscordClient")
    def test_upsert_notifies_once(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "99", "channel_id": "88"}
        mock_client.send_dm.return_value = mock_response

        first = upsert_feed_item(self.source, self._item(), now=timezone.now())
        second = upsert_feed_item(
            self.source, self._item(), now=timezone.now()
        )
        self.assertEqual(first["notified"], 1)
        self.assertEqual(second["notified"], 0)
        self.assertEqual(mock_client.send_dm.call_count, 1)
        event = NpsiExternalEvent.objects.get()
        self.assertEqual(event.status, NpsiExternalEvent.Status.NOTIFIED)
        payload = mock_client.send_dm.call_args.kwargs["payload"]
        self.assertEqual(
            payload["components"][0]["components"][0]["label"],
            "Post to schedule",
        )
        self.assertIn(
            "npsi:create:",
            payload["components"][0]["components"][0]["custom_id"],
        )

    @patch("fleets.helpers.npsi_ingest.DiscordClient")
    def test_skips_past_events(self, mock_client_cls):
        past = timezone.now() - timedelta(days=1)
        result = upsert_feed_item(
            self.source,
            self._item(start=past.strftime("%Y-%m-%dT%H:%M:%S.000Z")),
            now=timezone.now(),
        )
        self.assertEqual(result["skipped"], 1)
        self.assertFalse(NpsiExternalEvent.objects.exists())
        mock_client_cls.return_value.send_dm.assert_not_called()

    def test_fingerprint_stable(self):
        start = timezone.now()
        a = event_fingerprint(1, start, "Roaming Navies")
        b = event_fingerprint(1, start, "Roaming Navies")
        self.assertEqual(a, b)

    @patch("fleets.helpers.npsi_ingest.DiscordClient")
    def test_skips_when_no_audience(self, mock_client_cls):
        self.source.default_audience = None
        self.source.save()
        result = upsert_feed_item(
            self.source, self._item(), now=timezone.now()
        )
        self.assertEqual(result["skipped"], 1)
        event = NpsiExternalEvent.objects.get()
        self.assertEqual(event.status, NpsiExternalEvent.Status.SKIPPED)
        mock_client_cls.return_value.send_dm.assert_not_called()

    @patch("fleets.helpers.npsi_ingest.requests.get")
    @patch("fleets.helpers.npsi_ingest.DiscordClient")
    def test_disabled_source_is_not_polled(self, mock_client_cls, mock_get):
        self.source.enabled = False
        self.source.save()
        stats = poll_npsi_sources()
        self.assertEqual(stats["sources"], 0)
        mock_get.assert_not_called()
        mock_client_cls.return_value.send_dm.assert_not_called()

    @patch("fleets.helpers.npsi_ingest.DiscordClient")
    def test_unresolvable_fc_is_skipped(self, mock_client_cls):
        result = upsert_feed_item(
            self.source,
            self._item(character_name="Unknown Pilot"),
            now=timezone.now(),
        )
        self.assertEqual(result["skipped"], 1)
        event = NpsiExternalEvent.objects.get()
        self.assertEqual(event.status, NpsiExternalEvent.Status.SKIPPED)
        self.assertIn("not linked", event.skip_reason)
        mock_client_cls.return_value.send_dm.assert_not_called()


class NpsiDiscordApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.audience = EveFleetAudience.objects.get(name="Test Audience")
        self.staff = User.objects.create(username="bot_service", is_staff=True)
        self.staff_token = jwt.encode(
            {"user_id": self.staff.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        self.bystander = User.objects.create(username="bystander")
        DiscordUser.objects.create(
            id=2003, discord_tag="bystander", user=self.bystander
        )
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_evefleet")
        )
        corp = EveCorporation.objects.create(
            corporation_id=1, name="Test Corp"
        )
        char = EveCharacter.objects.create(
            character_id=111,
            character_name="Vex Drake",
            user=self.user,
            corporation_id=corp.corporation_id,
        )
        set_primary_character(self.user, char)
        DiscordUser.objects.create(id=4242, discord_tag="vex", user=self.user)
        self.source, _ = NpsiEventSource.objects.update_or_create(
            name="Unaligned",
            defaults={
                "feed_url": "https://example.test/events",
                "fc_character_name": "Vex Drake",
                "default_audience": self.audience,
                "default_type": "non_strategic",
            },
        )
        self.event = NpsiExternalEvent.objects.create(
            source=self.source,
            fingerprint="abc",
            summary="Roaming Navies",
            description="Roaming through nullsec",
            location_text="Jita",
            character_name="Vex Drake",
            start_time=timezone.now() + timedelta(days=6),
            status=NpsiExternalEvent.Status.NOTIFIED,
        )

    def _post(self, path, discord_user_id, token=None):
        return self.client.post(
            f"/api/fleets{path}",
            data=json.dumps({"discord_user_id": discord_user_id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token or self.staff_token}",
        )

    @patch("fleets.helpers.npsi_actions.DiscordClient")
    def test_fc_can_post_to_schedule(self, mock_discord):
        response = self._post(
            f"/npsi-events/{self.event.id}/discord-create", 4242
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, NpsiExternalEvent.Status.CREATED)
        fleet = EveFleet.objects.get(id=self.event.eve_fleet_id)
        self.assertEqual(fleet.created_by_id, self.user.id)
        self.assertEqual(fleet.audience_id, self.audience.id)
        self.assertIn("Roaming through nullsec", fleet.description)

    def test_wrong_discord_user_rejected(self):
        response = self._post(
            f"/npsi-events/{self.event.id}/discord-create", 2003
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(EveFleet.objects.exists())

    @patch("fleets.helpers.npsi_actions.send_discord_pre_ping")
    @patch("fleets.helpers.npsi_actions.DiscordClient")
    def test_preping_requires_posted_fleet(self, mock_discord, mock_preping):
        mock_preping.return_value = True
        response = self._post(
            f"/npsi-events/{self.event.id}/discord-preping", 4242
        )
        self.assertEqual(response.status_code, 400)
        self._post(f"/npsi-events/{self.event.id}/discord-create", 4242)
        response = self._post(
            f"/npsi-events/{self.event.id}/discord-preping", 4242
        )
        self.assertEqual(response.status_code, 200, response.content)
        mock_preping.assert_called_once()

    @patch("fleets.helpers.npsi_actions.DiscordClient")
    def test_tracking_requires_posted_fleet(self, mock_discord):
        response = self._post(
            f"/npsi-events/{self.event.id}/discord-tracking", 4242
        )
        self.assertEqual(response.status_code, 400)

    @patch("fleets.models.EveFleet.start")
    @patch("fleets.helpers.npsi_actions.DiscordClient")
    def test_tracking_rejected_for_bystander(self, mock_discord, mock_start):
        self._post(f"/npsi-events/{self.event.id}/discord-create", 4242)
        response = self._post(
            f"/npsi-events/{self.event.id}/discord-tracking", 2003
        )
        self.assertEqual(response.status_code, 403)
        mock_start.assert_not_called()
