import ast
import logging
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
from unittest.mock import patch, MagicMock

import factory
import jwt

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import signals
from django.test import Client, SimpleTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.contrib.auth.models import User, Permission
from django.utils import timezone

from app.celery import app as celery_app
from app.test import TestCase
from users.helpers import add_user_permission
from eveonline.client import EsiResponse
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveLocation,
    EvePlayer,
)
from eveonline.helpers.characters import set_primary_character
from discord.models import DiscordUser

# from groups.models import Team
# from groups.helpers import TECH_TEAM
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
)
from fleets.endpoints.helpers import (
    fixup_fleet_status,
    time_region,
)
from fleets.endpoints.schemas import EveFleetTrackingResponse
from fleets.signals import (
    update_fleet_schedule_on_save,
    update_fleet_schedule_on_delete,
)
from fleets.helpers.fleet_location import backfill_missing_fleet_locations
from fleets.motd import get_motd
from fleets.notifications import get_fleet_discord_notification
from fleets.tasks import (
    SCHEDULE_REFRESH_DELAY_SECONDS,
    get_fleet_emoji,
    update_fleet_schedule,
    update_fleet_instances,
)
from fittings.models import EveDoctrine

BASE_URL = "/api/fleets"

logger = logging.getLogger(__name__)


def disconnect_fleet_signals():
    """Disconnect signals that would try to call Discord or ESI"""
    signals.post_save.disconnect(
        sender=EveFleet,
        dispatch_uid="update_fleet_schedule_on_save",
    )
    signals.post_delete.disconnect(
        update_fleet_schedule_on_delete,
        sender=EveFleet,
    )
    signals.post_save.disconnect(
        sender=EveCharacter,
        dispatch_uid="populate_eve_character_public_data",
    )
    signals.post_save.disconnect(
        sender=EveCharacter,
        dispatch_uid="populate_eve_character_private_data",
    )


def setup_fleet_reference_data():
    """Create reference data needed for fleets"""
    EveLocation.objects.create(
        location_id=123,
        location_name="Test Location",
        solar_system_id=234,
        solar_system_name="Somewhere",
        short_name="Somewhere",
        staging_active=True,
        fleets_active=True,
    )

    EveFleetAudience.objects.create(
        name="Test Audience",
        discord_channel_name="TestChannel",
    )
    EveFleetAudience.objects.create(
        name="Hidden",
        hidden=True,
        add_to_schedule=False,
    )


def setup_fc(user):
    character_id = 1234

    user.user_permissions.add(Permission.objects.get(codename="add_evefleet"))
    corp = EveCorporation.objects.create(corporation_id=1, name="Test Corp")
    character = EveCharacter.objects.create(
        character_id=character_id,
        character_name="Mr FC",
        user=user,
        corporation_id=corp.corporation_id,
    )
    set_primary_character(user, character)

    DiscordUser.objects.create(
        id=1,
        discord_tag="MrFC",
        user=user,
    )

    return character_id


def make_test_fleet(
    description: str, fc_user: User, start: datetime = None
) -> EveFleet:
    if start is None:
        start = timezone.now() + timedelta(hours=1)

    location = EveLocation.objects.filter(staging_active=True).first()

    return EveFleet.objects.create(
        start_time=start,
        description=description,
        type="training",
        status="pending",
        created_by=fc_user,
        audience=EveFleetAudience.objects.first(),
        location=location,
        # New fleets hide their roster; these fixtures predate that.
        hide_volunteers=False,
    )


class FleetHelperTestCase(SimpleTestCase):
    """Tests for Fleet helper code"""

    @override_settings(WEB_LINK_URL="https://my.minmatar.org")
    def test_get_motd_is_compact(self):
        """No role nag or quote: MOTD real estate is for fleet info."""
        motd = get_motd(
            1,
            "FC Name",
            None,
            None,
            "https://discord.gg/minmatar",
            "Minmatar Fleet Discord",
            "https://example.com/d",
            "Doctrine",
        )
        self.assertNotIn("fleet roles are missing", motd)
        self.assertNotIn("Rat", motd.split("Doctrine", 1)[1])
        self.assertFalse(motd.endswith("\n"))
        self.assertIn(
            '<loc><a href="https://my.minmatar.org/learning/guides/'
            'new-player-fleet-guide/">New Player Fleet Guide</a></loc>',
            motd,
        )

    def test_get_motd_shows_set_doctrine_link_when_no_doctrine(self):
        motd = get_motd(
            1,
            "FC Name",
            None,
            None,
            "https://discord.gg/minmatar",
            "Minmatar Fleet Discord",
            None,
            None,
            fleet_edit_url="https://my.minmatar.org/fleets/upcoming/edit/42",
        )
        self.assertIn("Set the doctrine", motd)
        self.assertIn("https://my.minmatar.org/fleets/upcoming/edit/42", motd)

    def test_discord_notification_template(self):
        notification = get_fleet_discord_notification(
            fleet_id=123,
            fleet_type="training",
            fleet_location="Jita",
            fleet_audience="Alliance",
            fleet_commander_name="Fleet Commander",
            fleet_commander_id=1234,
            fleet_description="Test fleet",
            fleet_voice_channel="Voice 1",
            fleet_voice_channel_link="link",
        )
        self.assertEqual("@everyone", notification["content"])


class FleetEmojiTestCase(SimpleTestCase):
    """The schedule's fleet-type emoji must be keyed by the stored fleet type."""

    def _settings_example_emoji_keys(self):
        path = (
            Path(__file__).resolve().parent.parent
            / "app"
            / "settings.py.example"
        )
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "DISCORD_FLEET_EMOJIS"
            ):
                return [key.value for key in node.value.keys]
        self.fail("DISCORD_FLEET_EMOJIS not found in settings.py.example")
        return []

    def test_emoji_keys_are_fleet_types(self):
        fleet_types = {value for value, _ in EveFleet.fleet_types}
        keys = self._settings_example_emoji_keys()
        self.assertIn("non_strategic", keys)
        for key in keys:
            self.assertIn(key, fleet_types)

    @patch("fleets.tasks.settings")
    def test_non_strategic_fleet_gets_its_emoji(self, settings_mock):
        settings_mock.DISCORD_FLEET_EMOJIS = {
            "non_strategic": {"name": "non_strategic", "id": 123},
        }
        self.assertEqual(
            get_fleet_emoji("non_strategic"), "<:non_strategic:123>"
        )


class FleetSignalsTestCase(TestCase):
    """Tests for fleet signals"""

    def _schedule_fleet_mock(self, *, on_schedule: bool):
        instance = MagicMock(spec=EveFleet)
        instance.invite_only = False
        instance.status = "pending"
        instance.host_group_id = None
        instance.open_to_alliance = False
        instance.on_schedule = False
        instance.audience = MagicMock()
        instance.audience.add_to_schedule = on_schedule
        return instance

    @patch("fleets.tasks.discord_client")
    def test_update_fleet_schedule_on_save(self, discord_mock):
        instance = self._schedule_fleet_mock(on_schedule=False)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            update_fleet_schedule_on_save(None, instance, False)

        # Should not be called when add_to_schedule is False
        self.assertEqual([], callbacks)
        discord_mock.get_messages.assert_not_called()

        instance = self._schedule_fleet_mock(on_schedule=True)
        discord_mock.get_messages.return_value = []

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            update_fleet_schedule_on_save(None, instance, False)

        # The save only queues the refresh; a worker talks to Discord.
        discord_mock.get_messages.assert_not_called()
        for callback in callbacks:
            callback()

        # Should be called when add_to_schedule is True
        discord_mock.get_messages.assert_called_once()
        discord_mock.create_message.assert_called_once()

    @patch("fleets.tasks.discord_client")
    def test_private_fleet_save_skips_schedule_refresh(self, discord_mock):
        instance = self._schedule_fleet_mock(on_schedule=True)
        instance.invite_only = True

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            update_fleet_schedule_on_save(None, instance, False)

        self.assertEqual([], callbacks)
        discord_mock.get_messages.assert_not_called()

    @patch("fleets.tasks.discord_client")
    def test_update_fleet_schedule_on_delete(self, discord_mock):
        instance = self._schedule_fleet_mock(on_schedule=True)
        discord_mock.get_messages.return_value = []

        with self.captureOnCommitCallbacks(execute=True):
            update_fleet_schedule_on_delete(None, instance)

        discord_mock.get_messages.assert_called_once()
        discord_mock.create_message.assert_called_once()

    @patch("celery.app.task.Task.apply_async")
    def test_saves_share_one_queued_schedule_refresh(self, apply_async):
        """Saves made before the refresh runs queue it once, after a short
        delay, so Discord sees one delete-and-repost."""
        instance = self._schedule_fleet_mock(on_schedule=True)
        # Dedupe only applies when publishing to a broker, not eager runs.
        eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = False
        self.addCleanup(setattr, celery_app.conf, "task_always_eager", eager)
        lock_key = update_fleet_schedule.queued_key((), {})
        cache.delete(lock_key)
        self.addCleanup(cache.delete, lock_key)

        with self.captureOnCommitCallbacks(execute=True):
            update_fleet_schedule_on_save(None, instance, False)
            update_fleet_schedule_on_save(None, instance, False)

        apply_async.assert_called_once()
        self.assertEqual(
            SCHEDULE_REFRESH_DELAY_SECONDS,
            apply_async.call_args.kwargs["countdown"],
        )

    @patch("fleets.tasks.queue_fleet_schedule_refresh")
    def test_editing_a_private_fleet_does_not_refresh_schedule(self, queue):
        """Invite-only fleets are never on #schedule; editing them must not
        delete-and-repost the channel."""
        setup_fleet_reference_data()
        audience = EveFleetAudience.objects.get(name="Test Audience")
        self.assertTrue(audience.add_to_schedule)
        fleet = EveFleet.objects.create(
            type="strategic",
            description="Quiet drop",
            start_time=timezone.now() + timedelta(hours=4),
            created_by=self.user,
            audience=audience,
            status="pending",
            invite_only=True,
        )
        queue.reset_mock()
        fleet.description = "Quiet drop, amended"
        fleet.save()
        queue.assert_not_called()


def patch_fleet_esi(test):
    """Patch EsiClient for a fleet start: the boss check
    (fleets.helpers.fleet_boss) and the fleet updates (fleets.models) share
    one mock, passed as the test's last argument. Put it below any other
    @patch, so their mocks come first as before."""

    @wraps(test)
    def wrapper(self, *args):
        esi_mock = MagicMock()
        with patch("fleets.models.EsiClient", esi_mock), patch(
            "fleets.helpers.fleet_boss.EsiClient", esi_mock
        ):
            return test(self, *args, esi_mock)

    return wrapper


class FleetRouterTestCase(TestCase):
    """Test cases for the fleet router."""

    def setUp(self):
        # create test client
        self.client = Client()

        disconnect_fleet_signals()

        setup_fleet_reference_data()

        super().setUp()

        add_user_permission(self.user, "view_evefleet")

    def test_deprecated_fleet_list_routes_removed(self):
        make_test_fleet("Test fleet 1", self.user)

        response = self.client.get(
            f"{BASE_URL}?upcoming=true",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(405, response.status_code)

        response = self.client.get(
            f"{BASE_URL}/v2?upcoming=true",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(422, response.status_code)

    def test_get_fleets_v3(self):
        make_test_fleet("Test fleet 1", self.user)
        make_test_fleet("Test fleet 2", self.user)

        response = self.client.get(
            f"{BASE_URL}/v3?fleet_filter=upcoming",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        fleets = response.json()
        # logger.info("fleets v3 response = %s", fleets)
        self.assertEqual(2, len(fleets))

    def test_get_fleets_v3_includes_doctrine_id(self):
        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type="non_strategic",
            description="A test doctrine",
        )
        fleet = make_test_fleet("Test fleet", self.user)
        fleet.doctrine = doctrine
        fleet.save()

        response = self.client.get(
            f"{BASE_URL}/v3?fleet_filter=upcoming",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        fleets = response.json()
        self.assertEqual(1, len(fleets))
        self.assertEqual(doctrine.id, fleets[0]["doctrine_id"])

    def test_get_fleets_v3_names_fc_and_doctrine(self):
        """The schedule carries the FC's primary character and the doctrine
        name, so clients need no profile or doctrine lookups."""
        doctrine = EveDoctrine.objects.create(
            name="Hurricanes", type="non_strategic", description=""
        )
        fc = User.objects.create(username="fc_with_main")
        character = EveCharacter.objects.create(
            character_id=9001, character_name="FC Main", user=fc
        )
        EvePlayer.objects.create(
            user=fc, primary_character=character, nickname="fc_with_main"
        )
        named = make_test_fleet("With FC", fc)
        named.doctrine = doctrine
        named.save()
        no_main = make_test_fleet("No main", User.objects.create(username="x"))

        response = self.client.get(
            f"{BASE_URL}/v3?fleet_filter=upcoming",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        by_id = {fleet["id"]: fleet for fleet in response.json()}
        self.assertEqual(9001, by_id[named.id]["fleet_commander_character_id"])
        self.assertEqual("FC Main", by_id[named.id]["fleet_commander_name"])
        self.assertEqual("Hurricanes", by_id[named.id]["doctrine_name"])
        self.assertEqual(fc.id, by_id[named.id]["fleet_commander"])
        self.assertIsNone(by_id[no_main.id]["fleet_commander_character_id"])
        self.assertIsNone(by_id[no_main.id]["fleet_commander_name"])
        self.assertIsNone(by_id[no_main.id]["doctrine_name"])

    def test_get_fleets_v3_names_cost_no_query_per_fleet(self):
        """FC and doctrine names come from the list query (select_related),
        so only tracking still costs queries per fleet."""
        doctrine = EveDoctrine.objects.create(
            name="Hurricanes", type="non_strategic", description=""
        )

        def count_queries(fleets):
            for n in range(fleets):
                fc = User.objects.create(username=f"fc{fleets}_{n}")
                character = EveCharacter.objects.create(
                    character_id=1000 * fleets + n,
                    character_name=f"FC {n}",
                    user=fc,
                )
                EvePlayer.objects.create(
                    user=fc, primary_character=character, nickname=fc.username
                )
                fleet = make_test_fleet(f"Fleet {n}", fc)
                fleet.doctrine = doctrine
                fleet.save()
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(
                    f"{BASE_URL}/v3?fleet_filter=upcoming",
                    HTTP_AUTHORIZATION=f"Bearer {self.token}",
                )
            EveFleet.objects.all().delete()
            self.assertEqual(fleets, len(response.json()))
            return len(queries)

        one, three = count_queries(1), count_queries(3)
        # Each fleet still checks for a tracking instance (exists()).
        self.assertLessEqual(three - one, 2 * 1)

    def test_get_fleet(self):
        fleet = make_test_fleet("Test fleet", self.user)

        response = self.client.get(
            f"{BASE_URL}/{fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(fleet.id, response.json()["id"])
        self.assertEqual("Test fleet", response.json()["description"])
        self.assertIsNone(response.json().get("objective"))

    def test_get_fleet_includes_objective(self):
        fleet = make_test_fleet("Test fleet", self.user)
        fleet.objective = "Take the objective"
        fleet.save()

        response = self.client.get(
            f"{BASE_URL}/{fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("Take the objective", response.json()["objective"])

    def test_get_fleet_with_null_audience(self):
        fleet = make_test_fleet("Test fleet", self.user)
        fleet.audience = None
        fleet.save()

        response = self.client.get(
            f"{BASE_URL}/{fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.json()["audience"])

    def test_create_fleet_with_objective(self):
        setup_fc(self.user)
        audience = EveFleetAudience.objects.first()
        data = {
            "type": "training",
            "description": "Test fleet",
            "objective": "Short tagline here",
            "start_time": timezone.now().isoformat(),
            "audience_id": audience.id,
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("Short tagline here", response.json()["objective"])
        fid = response.json()["id"]
        self.assertEqual(
            "Short tagline here",
            EveFleet.objects.get(id=fid).objective,
        )

    def test_patch_fleet_objective(self):
        self.user.is_superuser = True
        self.user.save()
        fleet = make_test_fleet("Test fleet", self.user)

        response = self.client.patch(
            f"{BASE_URL}/{fleet.id}",
            {"objective": "Updated tagline"},
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("Updated tagline", response.json()["objective"])
        fleet.refresh_from_db()
        self.assertEqual("Updated tagline", fleet.objective)

    def test_fleet_metrics_for_one_fleet(self):
        setup_fc(self.user)
        first = make_test_fleet("First", self.user)
        second = make_test_fleet("Second", self.user)

        everything = self.client.get(
            f"{BASE_URL}/metrics",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        response = self.client.get(
            f"{BASE_URL}/metrics?fleet_id={second.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {first.id, second.id}, {row["fleet_id"] for row in everything}
        )
        self.assertEqual(
            [row for row in everything if row["fleet_id"] == second.id],
            response.json(),
        )

    def test_commander_metrics_available_without_privilege(self):
        response = self.client.get(
            f"{BASE_URL}/commander-metrics",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

    def test_commander_metrics_month_counts(self):
        self.user.is_superuser = True
        self.user.save()
        setup_fc(self.user)
        char = EveCharacter.objects.get(user=self.user)
        player, created = EvePlayer.objects.get_or_create(
            user=self.user,
            defaults={
                "nickname": f"cmdmetrics_{self.user.pk}",
                "primary_character": char,
            },
        )
        if not created:
            player.primary_character = char
            player.save(update_fields=["primary_character"])

        make_test_fleet("A", self.user)
        make_test_fleet("B", self.user)
        make_test_fleet(
            "Old",
            self.user,
            start=timezone.now() - timedelta(days=40),
        )
        cancelled = make_test_fleet("X", self.user)
        cancelled.status = "cancelled"
        cancelled.save()

        response = self.client.get(
            f"{BASE_URL}/commander-metrics",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        rows = response.json()
        mine = [r for r in rows if r["user_id"] == self.user.id]
        self.assertEqual(1, len(mine))
        self.assertEqual(2, mine[0]["fleet_count"])
        self.assertEqual(char.character_id, mine[0]["primary_character_id"])
        self.assertEqual(
            char.character_name, mine[0]["primary_character_name"]
        )
        self.assertEqual(1, mine[0]["corporation_id"])
        self.assertEqual("Test Corp", mine[0]["corporation_name"])

    def test_patch_fleet(self):
        self.user.is_superuser = True
        self.user.save()

        fleet = make_test_fleet("Test fleet", self.user)

        logger.info("Created test fleet %d", fleet.id)

        self.assertEqual("Test fleet", fleet.description)

        update = {
            "description": "Updated",
            "aar_link": "https://discord/channel/thread",
        }

        response = self.client.patch(
            f"{BASE_URL}/{fleet.id}",
            update,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)

        updated_fleet = EveFleet.objects.filter(id=fleet.id).first()

        self.assertEqual("Updated", updated_fleet.description)

    @patch("fleets.endpoints.fleet.patch_fleet.try_refresh_active_fleet_motd")
    def test_patch_fleet_doctrine_refreshes_motd(self, refresh_mock):
        self.user.is_superuser = True
        self.user.save()

        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type="non_strategic",
            description="A test doctrine",
        )
        fleet = make_test_fleet("Test fleet", self.user)

        response = self.client.patch(
            f"{BASE_URL}/{fleet.id}",
            {"doctrine_id": doctrine.id},
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(doctrine.id, response.json()["doctrine_id"])
        refresh_mock.assert_called_once()
        self.assertEqual(fleet.id, refresh_mock.call_args[0][0].id)

    def test_fixup_fleet_status(self):
        self.assertEqual(None, fixup_fleet_status(None, None))
        fleet = make_test_fleet("Test", self.user)
        fleet.status = "active"
        tracking = None
        self.assertEqual("active", fixup_fleet_status(fleet, tracking))
        tracking = EveFleetTrackingResponse(
            id=1,
            start_time=timezone.now(),
            end_time=timezone.now(),
            is_registered=True,
        )
        self.assertEqual("complete", fixup_fleet_status(fleet, tracking))

    def test_get_fleet_reference_data(self):
        setup_fc(self.user)

        response = self.client.get(
            f"{BASE_URL}/types",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

        response = self.client.get(
            f"{BASE_URL}/v2/locations",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertGreaterEqual(len(response.json()), 1)

        response = self.client.get(
            f"{BASE_URL}/audiences",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.json()))
        self.assertEqual("Test Audience", response.json()[0]["display_name"])

    def test_create_fleet_endpoint(self):
        setup_fc(self.user)

        location = EveLocation.objects.filter(staging_active=True).first()
        audience = EveFleetAudience.objects.first()

        # Test creating fleet with location_id (backward compatibility)
        data = {
            "type": "training",
            "description": "Test fleet",
            "start_time": timezone.now(),
            "audience_id": audience.id,
            "location_id": location.location_id,
        }

        response = self.client.post(
            f"{BASE_URL}",
            data,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fleet_response = response.json()
        self.assertTrue(fleet_response["id"])
        self.assertEqual("Test Location", fleet_response["location"])

        db_fleet = EveFleet.objects.filter(id=fleet_response["id"]).first()
        self.assertIsNotNone(db_fleet)

    def test_create_fleet_without_location_id_uses_staging_active(self):
        setup_fc(self.user)

        audience = EveFleetAudience.objects.first()
        staging = EveLocation.objects.filter(staging_active=True).first()
        self.assertIsNotNone(staging)

        data = {
            "type": "training",
            "description": "Test fleet without location_id",
            "start_time": timezone.now(),
            "audience_id": audience.id,
        }

        response = self.client.post(
            f"{BASE_URL}",
            data,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fleet_response = response.json()
        self.assertTrue(fleet_response["id"])
        self.assertEqual("Test Location", fleet_response["location"])

        db_fleet = EveFleet.objects.filter(id=fleet_response["id"]).first()
        self.assertIsNotNone(db_fleet)
        self.assertEqual(db_fleet.location_id, staging.location_id)

    def test_backfill_missing_fleet_locations_uses_staging_active(self):
        staging = EveLocation.objects.filter(staging_active=True).first()
        self.assertIsNotNone(staging)

        fleet = EveFleet.objects.create(
            type="non_strategic",
            description="Legacy fleet without location",
            start_time=timezone.now() + timedelta(hours=1),
            created_by=self.user,
            audience=EveFleetAudience.objects.first(),
            location=None,
            status="pending",
        )
        self.assertIsNone(fleet.location_id)

        updated = backfill_missing_fleet_locations()
        self.assertEqual(updated, 1)

        fleet.refresh_from_db()
        self.assertEqual(fleet.location_id, staging.location_id)

    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_start_fleet_endpoint(self, discord_mock, esi_mock):
        char_id = setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.save()
        fleet.audience.discord_channel_id = 4242
        fleet.audience.save()

        esi_mock_instance = esi_mock.return_value
        esi_mock_instance.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": fleet.id,
                "fleet_boss_id": char_id,
            },
        )
        esi_mock_instance.update_fleet_details.return_value = EsiResponse(
            response_code=204, data={}
        )

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                f"{BASE_URL}/{fleet.id}/tracking",
                data=None,
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(200, response.status_code)

        # Starting the fleet queues the audience ping; a worker posts it,
        # so a slow Discord can neither delay nor fail the start.
        discord_mock.assert_not_called()
        for callback in callbacks:
            callback()
        discord_mock.return_value.create_message.assert_called_once()
        call = discord_mock.return_value.create_message.call_args
        self.assertEqual(4242, call.kwargs["channel_id"])
        self.assertEqual(
            "INCOMING PING TRANSMISSION...",
            call.kwargs["payload"]["embeds"][0]["title"],
        )

    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_start_fleet_when_not_in_fleet(self, discord_mock, esi_mock):
        setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.save()

        esi_mock_instance = esi_mock.return_value
        esi_mock_instance.get_active_fleet.return_value = EsiResponse(
            response_code=404,
            data={
                "error": "Character is not in a fleet",
            },
        )
        esi_mock_instance.update_fleet_details.return_value = EsiResponse(
            response_code=204, data={}
        )

        response = self.client.post(
            f"{BASE_URL}/{fleet.id}/tracking",
            data=None,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(400, response.status_code)
        error = response.json()
        self.assertEqual("Not currently in a fleet", error["detail"])

    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_start_fleet_rejects_non_commander(self, discord_mock, esi_mock):
        char_id = setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.save()

        owner = User.objects.create(username="real_fc")
        owner_fleet = make_test_fleet("Owner fleet", owner)
        existing = EveFleetInstance.objects.create(
            id=987654,
            eve_fleet=owner_fleet,
            boss_id=9999,
        )

        esi_mock_instance = esi_mock.return_value
        esi_mock_instance.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": existing.id,
                "fleet_boss_id": 9999,
                "role": "squad_member",
            },
        )

        response = self.client.post(
            f"{BASE_URL}/{fleet.id}/tracking",
            data=None,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            "Must be the fleet commander of your in-game fleet",
            response.json()["detail"],
        )

        existing.refresh_from_db()
        self.assertEqual(owner_fleet.id, existing.eve_fleet_id)
        self.assertEqual(9999, existing.boss_id)
        self.assertNotEqual(char_id, existing.boss_id)

    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_start_fleet_now_as_commander(self, discord_mock, esi_mock):
        char_id = setup_fc(self.user)

        esi_mock_instance = esi_mock.return_value
        esi_mock_instance.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": 555666,
                "fleet_boss_id": char_id,
                "role": "fleet_commander",
            },
        )
        esi_mock_instance.update_fleet_details.return_value = EsiResponse(
            response_code=204, data={}
        )

        response = self.client.post(
            f"{BASE_URL}/start-now",
            {},
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fleet_id = response.json()["id"]
        instance = EveFleetInstance.objects.get(id=555666)
        self.assertEqual(fleet_id, instance.eve_fleet_id)
        self.assertEqual(char_id, instance.boss_id)

    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_start_fleet_now_rejects_non_commander(
        self, discord_mock, esi_mock
    ):
        setup_fc(self.user)

        owner = User.objects.create(username="real_fc")
        owner_fleet = make_test_fleet("Owner fleet", owner)
        existing = EveFleetInstance.objects.create(
            id=555666,
            eve_fleet=owner_fleet,
            boss_id=9999,
        )

        esi_mock_instance = esi_mock.return_value
        esi_mock_instance.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": existing.id,
                "fleet_boss_id": 9999,
                "role": "squad_member",
            },
        )

        fleets_before = EveFleet.objects.count()
        response = self.client.post(
            f"{BASE_URL}/start-now",
            {},
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            "Must be the fleet commander of your in-game fleet",
            response.json()["detail"],
        )
        self.assertEqual(fleets_before, EveFleet.objects.count())

        existing.refresh_from_db()
        self.assertEqual(owner_fleet.id, existing.eve_fleet_id)

    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_start_fleet_with_char(self, discord_mock, esi_mock):
        fc_id = setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.save()

        esi_mock_instance = esi_mock.return_value
        esi_mock_instance.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": fleet.id,
                "fleet_boss_id": fc_id,
            },
        )
        data = {
            "fc_character_id": fc_id,
        }
        response = self.client.post(
            f"{BASE_URL}/{fleet.id}/tracking",
            data,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)

    def add_fleet_member(
        self,
        instance: EveFleetInstance,
        char_id: int,
    ):
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=char_id,
            character_name=f"Pilot {char_id}",
            ship_type_id=1,
            solar_system_id=1,
            squad_id=1,
            wing_id=1,
            join_time=timezone.now(),
        )

    # def test_fleet_metrics(self):
    #     self.make_superuser()
    #     setup_fc(self.user)

    #     fleet = make_test_fleet("Test", self.user)
    #     fleet.start_time = datetime(
    #         2025, 1, 1, 21, 30, 0, 0, timezone.get_current_timezone()
    #     )
    #     fleet.save()
    #     instance = EveFleetInstance.objects.create(id=1, eve_fleet=fleet)
    #     self.add_fleet_member(instance, 1)
    #     self.add_fleet_member(instance, 2)

    #     response = self.client.get(
    #         f"{BASE_URL}/metrics",
    #         HTTP_AUTHORIZATION=f"Bearer {self.token}",
    #     )
    #     self.assertEqual(200, response.status_code)
    #     metrics = response.json()
    #     self.assertEqual(
    #         metrics,
    #         [
    #             {
    #                 "fleet_id": fleet.id,
    #                 "members": 2,
    #                 "time_region": "EU_US",
    #                 "location_name": "Test Location",
    #                 "status": "pending",
    #                 "fc_corp_name": "Test Corp",
    #                 "audience_name": "Test Audience",
    #             },
    #         ],
    #     )

    @patch("discord.outbox.DiscordClient")
    def test_fleet_preping(self, discord_mock):
        mock_client = MagicMock()
        discord_mock.return_value = mock_client
        self.make_superuser()
        setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.audience.discord_channel_id = 4242
        fleet.audience.save()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                f"{BASE_URL}/{fleet.id}/preping",
                "",
                "application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(202, response.status_code)

        # The request only queues the ping; a worker posts it.
        discord_mock.assert_not_called()
        for callback in callbacks:
            callback()

        mock_client.create_message.assert_called_once_with(
            channel_id=fleet.audience.discord_channel_id,
            payload=get_fleet_discord_notification(
                is_pre_ping=True,
                fleet_id=fleet.id,
                fleet_type=fleet.get_type_display(),
                fleet_location=(
                    fleet.formup_location.location_name
                    if fleet.formup_location
                    else "Ask FC"
                ),
                fleet_audience=fleet.audience.name,
                fleet_commander_name=fleet.fleet_commander.character_name,
                fleet_commander_id=fleet.fleet_commander.character_id,
                fleet_description=fleet.description,
                fleet_voice_channel=None,
                fleet_voice_channel_link=None,
                fleet_start_time=fleet.start_time,
            ),
        )

    def test_fleet_preping_without_audience_channel_fails(self):
        """Same answer as before: no channel to ping is an error."""
        self.make_superuser()
        setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.audience.discord_channel_id = None
        fleet.audience.save()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                f"{BASE_URL}/{fleet.id}/preping",
                "",
                "application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
        self.assertEqual(500, response.status_code)
        self.assertEqual([], callbacks)

    @patch("fleets.endpoints.active.current_fleets.EsiClient")
    def test_user_active_fleets(self, esi_client_class):
        esi_mock = esi_client_class.return_value

        esi_mock.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": 123456,
                "fleet_boss_id": 23456,
                "role": "squad_member",
            },
        )

        self.make_superuser()
        setup_fc(self.user)

        response = self.client.get(
            f"{BASE_URL}/current",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fleets = response.json()
        self.assertEqual(1, len(fleets))
        self.assertEqual("squad_member", fleets[0]["fleet_role"])

    def test_manually_close_fleet(self):
        self.make_superuser()
        setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)

        EveFleetInstance.objects.create(
            id=123456,
            eve_fleet=fleet,
        )

        update = {"status": "complete"}

        response = self.client.patch(
            f"{BASE_URL}/{fleet.id}",
            update,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)

        self.assertIsNotNone(EveFleetInstance.objects.get(id=123456).end_time)

    @patch_fleet_esi
    def test_start_fleet_error(self, esi_client_class):
        esi_mock = esi_client_class.return_value

        esi_mock.get_active_fleet.return_value = EsiResponse(
            response_code=599,
            data={"error": "Error getting fleet"},
        )

        setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.save()
        data = {}
        response = self.client.post(
            f"{BASE_URL}/{fleet.id}/tracking",
            data,
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual("Error starting fleet 1", response.json()["detail"])

    def test_get_v3_requires_view_evefleet(self):
        make_test_fleet("Listed", self.user)
        user_no_perm = User.objects.create(username="noperm_fleets")

        token = jwt.encode(
            {"user_id": user_no_perm.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        response = self.client.get(
            f"{BASE_URL}/v3?fleet_filter=upcoming",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(403, response.status_code)

    def test_get_fleet_requires_view_evefleet(self):
        viewer = User.objects.create(username="viewer")
        fc = User.objects.create(username="fc")
        fleet = make_test_fleet("FC fleet", fc)

        viewer_token = jwt.encode(
            {"user_id": viewer.id},
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        response = self.client.get(
            f"{BASE_URL}/{fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {viewer_token}",
        )
        self.assertEqual(403, response.status_code)

    def test_time_region(self):
        def hour_time(hour: int) -> datetime:
            return datetime(2025, 1, 1, hour, 30)

        self.assertEqual("US", time_region(hour_time(23)))
        self.assertEqual("US_AP", time_region(hour_time(6)))
        self.assertEqual("AP", time_region(hour_time(11)))
        self.assertEqual("EU", time_region(hour_time(17)))
        self.assertEqual("EU_US", time_region(hour_time(20)))

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_get_fleet_members(self):
        fleet = make_test_fleet("Test", self.user)
        instance = EveFleetInstance.objects.create(id=1, eve_fleet=fleet)
        self.add_fleet_member(instance, 1)

        response = self.client.get(
            f"{BASE_URL}/{fleet.id}/members",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("Pilot 1", data[0]["character_name"])


class FleetTaskTests(TestCase):
    """Tests of the Fleet background tasks."""

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("fleets.tasks.settings")
    def test_update_fleet_schedule_task(self, settings_mock):
        setup_fleet_reference_data()
        make_test_fleet(
            "Test fleet 1", self.user
        )  # pylint: disable=unused-variable

        fc = EveCharacter.objects.create(
            character_id=1234,
            character_name="Mr FC",
            user=self.user,
        )
        set_primary_character(self.user, fc)

        DiscordUser.objects.create(
            id=1,
            discord_tag="MrFC",
            user=self.user,
        )

        # Mock settings
        settings_mock.DISCORD_FLEET_SCHEDULE_CHANNEL_ID = 12345
        settings_mock.DISCORD_FLEET_EMOJIS = {
            "training": {"name": "training", "id": 999999},
        }

        # Patch the module-level constant that was set at import time
        with patch("fleets.tasks.FLEET_SCHEDULE_CHANNEL_ID", 12345):
            with patch("fleets.tasks.discord_client") as discord_mock:
                # Mock get_messages to return some messages
                discord_mock.get_messages.return_value = [
                    {"id": "123"},
                    {"id": "456"},
                ]

                update_fleet_schedule()

                # Verify Discord API calls
                discord_mock.get_messages.assert_called_once_with(12345)
                discord_mock.create_message.assert_called_once()
                # delete_message should be called for each message
                self.assertEqual(discord_mock.delete_message.call_count, 2)

                # Verify the message payload
                call_args = discord_mock.create_message.call_args
                self.assertEqual(call_args[0][0], 12345)  # channel_id
                payload = call_args[1]["payload"]

                # Verify message structure
                self.assertIn("content", payload)
                self.assertIn("components", payload)
                content = payload["content"]

                # Verify message starts with header
                self.assertTrue(content.startswith("## Fleet Schedule"))
                # Verify location grouping
                self.assertIn("**Test Location**", content)
                # Verify FC character name is included
                self.assertIn("Mr FC", content)
                # Verify emoji is included (if set)
                self.assertIn("<:training:999999>", content)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_fleet_member_update(self, discord, esi):
        esi_mock = esi.return_value

        fc_id = setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.status = "active"
        fleet.save()

        efi = EveFleetInstance.objects.create(
            id=1234,
            eve_fleet=fleet,
        )

        esi_mock.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": efi.id,
                "fleet_boss_id": fc_id,
            },
        )
        fleet_member_response = EsiResponse(
            response_code=200,
            data=[
                {
                    "character_id": fc_id,
                    "join_time": timezone.now(),
                    "role": "squad_member",
                    "role_name": "squad_member",
                    "ship_type_id": 1000,
                    "squad_id": 10,
                    "wing_id": 20,
                    "solar_system_id": 3001,
                    "station_id": 4001,
                    "takes_fleet_warp": True,
                }
            ],
        )
        esi_mock.get_fleet_members.return_value = fleet_member_response
        esi_mock.resolve_universe_names.return_value = EsiResponse(
            response_code=200,
            data=[
                {"id": fc_id, "name": "Mr FC"},
                {"id": 1000, "name": "X-Wing"},
                {"id": 3001, "name": "Homesystem"},
                {"id": 4001, "name": "Homestation"},
            ],
        )

        efi.update_fleet_members()

        self.assertEqual("active", efi.eve_fleet.status)

        efi.boss_id = fc_id
        efi.save()

        efi.update_fleet_members()

        self.assertEqual("active", efi.eve_fleet.status)

        esi_mock.get_fleet_members.return_value = EsiResponse(
            response_code=400,
            response="Mock error",
        )

        efi.update_fleet_members()

        self.assertEqual("active", efi.eve_fleet.status)

        esi_mock.get_active_fleet.return_value = EsiResponse(
            response_code=400,
        )

        EveFleetInstance.objects.filter(pk=efi.pk).update(
            start_time=timezone.now() - timedelta(hours=2)
        )
        efi.refresh_from_db()

        efi.update_fleet_members()

        self.assertEqual("complete", efi.eve_fleet.status)
        self.assertIsNotNone(efi.end_time)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_update_fleet_instances(self, discord, esi):
        esi_mock = esi.return_value

        fc_id = setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.status = "active"
        fleet.save()

        efi = EveFleetInstance.objects.create(
            id=1234,
            eve_fleet=fleet,
            end_time=None,
            boss_id=fc_id,
        )

        esi_mock.get_active_fleet.return_value = EsiResponse(
            response_code=200,
            data={
                "fleet_id": efi.id,
                "fleet_boss_id": fc_id,
            },
        )
        fleet_member_response = EsiResponse(
            response_code=200,
            data=[
                {
                    "character_id": fc_id,
                    "join_time": timezone.now(),
                    "role": "squad_member",
                    "role_name": "squad_member",
                    "ship_type_id": 1000,
                    "squad_id": 10,
                    "wing_id": 20,
                    "solar_system_id": 3001,
                    "station_id": 4001,
                    "takes_fleet_warp": True,
                }
            ],
        )
        esi_mock.get_fleet_members.return_value = fleet_member_response
        esi_mock.resolve_universe_names.return_value = EsiResponse(
            response_code=200,
            data=[
                {"id": fc_id, "name": "Mr FC"},
                {"id": 1000, "name": "X-Wing"},
                {"id": 3001, "name": "Homesystem"},
                {"id": 4001, "name": "Homestation"},
            ],
        )
        esi_mock.get_fleet.return_value = EsiResponse(
            response_code=200,
            data={"is_registered": True},
        )

        update_fleet_instances()

        fleet_member_response = EsiResponse(
            response_code=404,
            data="The fleet does not exist or you don't have access to it!",
        )

        EveFleetInstance.objects.filter(pk=efi.pk).update(
            start_time=timezone.now() - timedelta(hours=2)
        )

        update_fleet_instances()

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("discord.outbox.DiscordClient")
    @patch_fleet_esi
    def test_esi_failure_does_not_auto_close_within_one_hour(
        self, discord_mock, esi
    ):
        self.assertIsNotNone(discord_mock)
        esi_mock = esi.return_value
        fc_id = setup_fc(self.user)
        fleet = make_test_fleet("Test", self.user)
        fleet.disable_motd = True
        fleet.status = "active"
        fleet.save()

        efi = EveFleetInstance.objects.create(
            id=5555,
            eve_fleet=fleet,
            boss_id=fc_id,
        )
        esi_mock.get_fleet_members.return_value = EsiResponse(
            response_code=404,
            data={"error": "no access"},
        )
        esi_mock.get_active_fleet.return_value = EsiResponse(
            response_code=400,
        )

        efi.update_fleet_members()

        efi.refresh_from_db()
        fleet.refresh_from_db()
        self.assertIsNone(efi.end_time)
        self.assertEqual("active", fleet.status)


class FleetKillsRouterTestCase(TestCase):
    """GET /api/fleets/{id}/kills"""

    def setUp(self):
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        super().setUp()

    def test_not_found(self):
        add_user_permission(self.user, "view_evefleet")
        response = self.client.get(
            f"{BASE_URL}/999999/kills",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(404, response.status_code)

    def test_forbidden_without_fleet_access(self):
        other = User.objects.create(username="other")
        fleet = make_test_fleet("Someone else's fleet", other)
        response = self.client.get(
            f"{BASE_URL}/{fleet.id}/kills",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(403, response.status_code)

    def test_untracked_fleet_is_empty(self):
        fleet = make_test_fleet("Test fleet", self.user)
        response = self.client.get(
            f"{BASE_URL}/{fleet.id}/kills",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertFalse(body["tracked"])
        self.assertEqual(0, body["isk_destroyed"])
        self.assertEqual([], body["killmails"])
