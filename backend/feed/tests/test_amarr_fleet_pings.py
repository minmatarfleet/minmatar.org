from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from discord.models import DiscordChannel, DiscordGuild
from feed.helpers.amarr_fleet_pings import (
    AMARR_FLEET_ALERT_TITLE,
    build_amarr_fleet_alert_payload,
    maybe_notify_amarr_fleet,
)
from feed.models import FeedAmarrFleetAlert, FeedAmarrFleetPing, FeedEvent
from feed.rollups.types import RollupResult
from feed.rollups.writer import write_rollup_results
from ratelimit import RateLimitException


def make_amarr_fleet_ping_channel(
    *, channel_id: int = 555002
) -> DiscordChannel:
    guild, _ = DiscordGuild.objects.get_or_create(
        guild_id=999888778,
        defaults={"name": "Test Guild", "is_active": True},
    )
    return DiscordChannel.objects.create(
        channel_id=channel_id,
        guild=guild,
        name="amarr-fleets",
        channel_type=DiscordChannel.TEXT,
        receive_amarr_fleet_pings=True,
    )


def _amarr_event(
    *,
    cluster_key: str = "fleet_active:30002537:500003:2026-07-29T21:00",
    system_id: int = 30002537,
    system_name: str = "Amamake",
    title: str = "Medium Amarr fleet active",
    kills: int = 12,
    pilots: int = 15,
) -> FeedEvent:
    return FeedEvent.objects.create(
        kind=FeedEvent.Kind.FLEET_ACTIVE,
        occurred_at=timezone.now(),
        title=title,
        subheader=f"{system_name} · {kills} kills · {pilots} pilots · ~10m",
        preview="Medium fleet involving battlecruisers and frigates.",
        body="",
        accent=FeedEvent.Accent.AMARR,
        payload={
            "faction": "amarr",
            "system_id": system_id,
            "system_name": system_name,
            "kills": kills,
            "pilots": pilots,
            "roster": [
                {"character_id": 2111000001, "name": "Amarr Pilot"},
            ],
            "roster_total": pilots,
            "engagement_tier": "medium",
        },
        rollup_code="fleet_active",
        rollup_version=1,
        cluster_key=cluster_key,
        is_active=True,
    )


class AmarrFleetPingTestCase(TestCase):
    def setUp(self):
        make_amarr_fleet_ping_channel()

    def test_build_amarr_fleet_alert_payload(self):
        built = build_amarr_fleet_alert_payload(
            system_name="Amamake",
            title="Medium Amarr fleet active",
            subheader="Amamake · 12 kills · 15 pilots · ~10m",
            preview="Medium fleet involving battlecruisers.",
            kills=12,
            pilots=15,
            roster=[
                {"character_id": 2111000001, "name": "Amarr Pilot"},
            ],
            roster_total=15,
            systems=[
                {
                    "solar_system_id": 30002537,
                    "system_name": "Amamake",
                }
            ],
        )
        embed = built["embeds"][0]
        self.assertEqual(embed["title"], AMARR_FLEET_ALERT_TITLE)
        self.assertIn("**System:** Amamake", embed["description"])
        self.assertIn("Medium Amarr fleet active", embed["description"])
        self.assertIn(
            "[Amarr Pilot](https://zkillboard.com/character/2111000001/)",
            embed["description"],
        )
        self.assertIn("(+14 more)", embed["description"])

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_maybe_notify_creates_once_then_edits(self, mock_client_cls):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888701"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        first = _amarr_event(kills=12, pilots=15)
        self.assertTrue(maybe_notify_amarr_fleet(first))

        first.title = "Large Amarr fleet active"
        first.subheader = "Amamake · 20 kills · 22 pilots · ~18m"
        first.payload = {
            **first.payload,
            "kills": 20,
            "pilots": 22,
        }
        first.save()
        self.assertTrue(maybe_notify_amarr_fleet(first))

        self.assertEqual(FeedAmarrFleetAlert.objects.count(), 1)
        self.assertEqual(FeedAmarrFleetPing.objects.count(), 1)
        mock_client.create_message.assert_called_once()
        mock_client.update_message.assert_called_once()

        alert = FeedAmarrFleetAlert.objects.get()
        self.assertEqual(alert.kills, 20)
        self.assertEqual(alert.title, "Large Amarr fleet active")
        edit_payload = mock_client.update_message.call_args.kwargs["payload"]
        self.assertIn(
            "Large Amarr fleet active",
            edit_payload["embeds"][0]["description"],
        )

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_same_system_coalesces_different_cluster_keys(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888702"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        first = _amarr_event(
            cluster_key="fleet_active:30002537:500003:2026-07-29T21:00",
            kills=8,
            pilots=10,
        )
        second = _amarr_event(
            cluster_key="fleet_active:30002537:500003:2026-07-29T21:15",
            title="Heavy Amarr fleet active",
            kills=19,
            pilots=34,
        )

        self.assertTrue(maybe_notify_amarr_fleet(first))
        self.assertTrue(maybe_notify_amarr_fleet(second))

        self.assertEqual(FeedAmarrFleetAlert.objects.count(), 1)
        self.assertEqual(FeedAmarrFleetPing.objects.count(), 2)
        mock_client.create_message.assert_called_once()
        mock_client.update_message.assert_called_once()

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_skips_minmatar_and_non_fleet_events(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        militia = _amarr_event()
        militia.accent = FeedEvent.Accent.MILITIA
        militia.save()
        self.assertFalse(maybe_notify_amarr_fleet(militia))

        combat = _amarr_event(
            cluster_key="kill_burst:30002537:2026-07-29T21:00"
        )
        combat.kind = FeedEvent.Kind.KILLMAIL_BATCH
        combat.rollup_code = "kill_burst"
        combat.save()
        self.assertFalse(maybe_notify_amarr_fleet(combat))
        mock_client.create_message.assert_not_called()

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_skips_when_no_channel_configured(self, mock_client_cls):
        DiscordChannel.objects.all().delete()
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        event = _amarr_event()
        self.assertFalse(maybe_notify_amarr_fleet(event))
        mock_client.create_message.assert_not_called()
        self.assertEqual(FeedAmarrFleetAlert.objects.count(), 0)

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_skips_inactive_and_stale_fleets(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        inactive = _amarr_event(
            cluster_key="fleet_active:30002537:500003:2026-07-29T10:00"
        )
        inactive.is_active = False
        inactive.save()
        self.assertFalse(maybe_notify_amarr_fleet(inactive))

        stale = _amarr_event(
            cluster_key="fleet_active:30002537:500003:2026-07-29T11:00"
        )
        stale.occurred_at = timezone.now() - timedelta(hours=3)
        stale.save()
        self.assertFalse(maybe_notify_amarr_fleet(stale))
        mock_client.create_message.assert_not_called()

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_skips_already_pinged_cluster_without_session(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888704"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        event = _amarr_event()
        self.assertTrue(maybe_notify_amarr_fleet(event))
        alert = FeedAmarrFleetAlert.objects.get()
        # Expire the session so catch-up cannot open a second message.
        alert.last_activity_at = timezone.now() - timedelta(hours=2)
        alert.save(update_fields=["last_activity_at"])

        mock_client.create_message.reset_mock()
        mock_client.update_message.reset_mock()
        self.assertFalse(maybe_notify_amarr_fleet(event))
        mock_client.create_message.assert_not_called()
        mock_client.update_message.assert_not_called()
        self.assertEqual(FeedAmarrFleetAlert.objects.count(), 1)

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_skips_noop_discord_edit_within_min_interval(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888705"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        event = _amarr_event()
        self.assertTrue(maybe_notify_amarr_fleet(event))
        mock_client.create_message.assert_called_once()
        mock_client.update_message.reset_mock()

        # Same content shortly after create — no Discord PATCH.
        self.assertTrue(maybe_notify_amarr_fleet(event))
        mock_client.update_message.assert_not_called()
        alert = FeedAmarrFleetAlert.objects.get()
        self.assertEqual(alert.kills, 12)

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_edits_discord_after_min_interval_even_if_unchanged(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888706"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        event = _amarr_event()
        self.assertTrue(maybe_notify_amarr_fleet(event))
        alert = FeedAmarrFleetAlert.objects.get()
        alert.last_activity_at = timezone.now() - timedelta(minutes=3)
        alert.save(update_fields=["last_activity_at"])

        mock_client.update_message.reset_mock()
        self.assertTrue(maybe_notify_amarr_fleet(event))
        mock_client.update_message.assert_called_once()

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_writer_notifies_amarr_fleet_active(self, mock_client_cls):
        mock_client = MagicMock()
        create_response = MagicMock()
        create_response.json.return_value = {"id": "999888703"}
        mock_client.create_message.return_value = create_response
        mock_client_cls.return_value = mock_client

        cluster_key = "fleet_active:30002539:500003:2026-07-29T21:00"
        write_rollup_results(
            [
                RollupResult(
                    kind=FeedEvent.Kind.FLEET_ACTIVE,
                    occurred_at=timezone.now(),
                    title="Medium Amarr gang active",
                    subheader="Siseide · 16 kills · 15 pilots · ~11m",
                    preview="Medium gang involving frigates.",
                    body="",
                    accent=FeedEvent.Accent.AMARR,
                    payload={
                        "faction": "amarr",
                        "system_id": 30002539,
                        "system_name": "Siseide",
                        "kills": 16,
                        "pilots": 15,
                        "roster": [],
                        "roster_total": 15,
                    },
                    rollup_code="fleet_active",
                    rollup_version=1,
                    cluster_key=cluster_key,
                    is_active=True,
                )
            ]
        )

        self.assertEqual(FeedEvent.objects.count(), 1)
        self.assertEqual(FeedAmarrFleetAlert.objects.count(), 1)
        self.assertEqual(FeedAmarrFleetPing.objects.count(), 1)
        mock_client.create_message.assert_called_once()

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_rate_limit_logs_warning_not_exception(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.create_message.side_effect = RateLimitException(
            "Discord API rate limited", 1.0
        )
        event = _amarr_event()

        with patch("feed.helpers.amarr_fleet_pings.logger") as mock_logger:
            self.assertFalse(maybe_notify_amarr_fleet(event))
            mock_logger.warning.assert_called()
            mock_logger.exception.assert_not_called()

    @patch("feed.helpers.amarr_fleet_pings.DiscordClient")
    def test_writer_skips_historical_amarr_catchup(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        write_rollup_results(
            [
                RollupResult(
                    kind=FeedEvent.Kind.FLEET_ACTIVE,
                    occurred_at=timezone.now() - timedelta(hours=5),
                    title="Large Amarr gang active",
                    subheader="Vard · 14 kills · 23 pilots · ~19m",
                    preview="Large gang involving battlecruisers.",
                    body="",
                    accent=FeedEvent.Accent.AMARR,
                    payload={
                        "faction": "amarr",
                        "system_id": 30002538,
                        "system_name": "Vard",
                        "kills": 14,
                        "pilots": 23,
                        "roster": [],
                        "roster_total": 23,
                    },
                    rollup_code="fleet_active",
                    rollup_version=1,
                    cluster_key="fleet_active:30002538:500003:2026-07-29T12:00",
                    is_active=False,
                )
            ]
        )

        self.assertEqual(FeedEvent.objects.count(), 1)
        self.assertEqual(FeedAmarrFleetAlert.objects.count(), 0)
        mock_client.create_message.assert_not_called()
