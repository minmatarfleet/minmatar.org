"""Interim chiefs and chief volunteers.

A group without a chief shows its tribe chief as interim; a tribe without a
chief shows the alliance executor. Pilots volunteer for an open seat and the
executor appoints from the DM or the site.
"""

import importlib
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import Client, TestCase, override_settings

from app.testing import make_token
from discord.models import DiscordUser
from eveonline.models import EveCharacter, EvePlayer
from notifications.models import NotificationDelivery
from notifications.types.tribes import (
    TRIBE_CHIEF_VOLUNTEERED_KEY,
    render_chief_volunteered,
)
from tribes.helpers.chief_discord import appoint_custom_id
from tribes.helpers.chiefs import ChiefResolver
from tribes.models import (
    Tribe,
    TribeChiefVolunteer,
    TribeGroup,
    TribeGroupMembership,
)

BASE_URL = "/api/tribes"
EXECUTOR_CHARACTER_ID = 634915984


def setUpModule():
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import (  # noqa: PLC0415
        group_post_save,
        user_group_changed,
    )

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )
    django_signals.post_save.disconnect(
        group_post_save,
        sender=Group,
        dispatch_uid="group_post_save",
    )


def _pilot(username, character_id, name, discord_id=None):
    user = User.objects.create_user(username=username)
    character = EveCharacter.objects.create(
        character_id=character_id, character_name=name, user=user
    )
    EvePlayer.objects.create(
        user=user, primary_character=character, nickname=username
    )
    if discord_id:
        DiscordUser.objects.create(
            id=discord_id, discord_tag=f"{username}#1", user=user
        )
    return user


def _auth(user) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {make_token(user)}"}


@override_settings(ALLIANCE_EXECUTOR_CHARACTER_ID=EXECUTOR_CHARACTER_ID)
class ChiefVolunteerTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Notification workers run eagerly in tests: fake Discord for the
        # DM send and the answered-DM edit.
        channels_patch = patch("notifications.channels.DiscordClient")
        self.discord_cls = channels_patch.start()
        self.discord_cls.return_value.send_dm.return_value = {
            "id": "9",
            "channel_id": "8",
        }
        self.addCleanup(channels_patch.stop)
        acquire_patch = patch(
            "notifications.channels.acquire", return_value=(True, 0.0)
        )
        acquire_patch.start()
        self.addCleanup(acquire_patch.stop)
        tasks_patch = patch("tribes.tasks.discord")
        self.tasks_discord = tasks_patch.start()
        self.addCleanup(tasks_patch.stop)
        self.executor = _pilot(
            "bear", EXECUTOR_CHARACTER_ID, "BearThatCares", 700
        )
        self.tribe_chief = _pilot("faye", 92001, "Faye Vaelent", 701)
        self.pilot = _pilot("casper", 92002, "Casper Sullivan", 702)
        self.other = _pilot("zigg", 92003, "Zigg Omelo", 703)
        self.pulse = Tribe.objects.create(
            name="Pulse", slug="pulse-chiefs", chief=self.tribe_chief
        )
        self.fishermen = TribeGroup.objects.create(
            tribe=self.pulse, name="Fishermen", code="pulse.fish-chiefs"
        )
        self.supply = Tribe.objects.create(name="Supply", slug="supply-ch")
        self.freighters = TribeGroup.objects.create(
            tribe=self.supply, name="Freighters", code="supply.frt-chiefs"
        )

    def _group(self, group, user=None):
        kwargs = _auth(user) if user else {}
        return self.client.get(
            f"{BASE_URL}/{group.tribe_id}/groups/{group.pk}", **kwargs
        ).json()

    def _volunteer(self, user, tribe, group=None, note=""):
        return self.client.post(
            f"{BASE_URL}/{tribe.pk}/chief-volunteers",
            data={
                "tribe_group_id": group.pk if group else None,
                "note": note,
            },
            content_type="application/json",
            **_auth(user),
        )

    def test_acting_chief_falls_back_tribe_then_executor(self):
        resolver = ChiefResolver()
        fish = resolver.for_group(self.fishermen)
        self.assertEqual(fish.user, self.tribe_chief)
        self.assertTrue(fish.is_interim)
        freighters = resolver.for_group(self.freighters)
        self.assertEqual(freighters.user, self.executor)
        self.assertTrue(freighters.is_interim)
        supply = resolver.for_tribe(self.supply)
        self.assertEqual(supply.user, self.executor)
        self.assertTrue(supply.is_interim)
        self.fishermen.chief = self.pilot
        self.assertFalse(resolver.for_group(self.fishermen).is_interim)

    def test_group_payload_shows_interim_and_keeps_chief_empty(self):
        body = self._group(self.fishermen)
        self.assertIsNone(body["chief"])
        self.assertTrue(body["chief_is_interim"])
        self.assertEqual(
            body["acting_chief"]["character_name"], "Faye Vaelent"
        )
        self.assertFalse(body["can_appoint_chief"])

        body = self._group(self.freighters, self.executor)
        self.assertEqual(
            body["acting_chief"]["character_name"], "BearThatCares"
        )
        self.assertTrue(body["can_appoint_chief"])

    def test_hidden_roster_still_names_the_stand_in(self):
        self.fishermen.roster_hidden = True
        self.fishermen.save()
        body = self._group(self.fishermen)
        self.assertEqual(
            body["acting_chief"]["character_name"], "Faye Vaelent"
        )

    def test_tribe_payload_shows_executor_as_interim(self):
        body = self.client.get(
            f"{BASE_URL}/{self.supply.pk}", **_auth(self.executor)
        ).json()
        self.assertIsNone(body["chief"])
        self.assertTrue(body["chief_is_interim"])
        self.assertEqual(
            body["acting_chief"]["character_name"], "BearThatCares"
        )
        self.assertTrue(body["can_appoint_chief"])
        body = self.client.get(f"{BASE_URL}/{self.pulse.pk}").json()
        self.assertFalse(body["chief_is_interim"])
        self.assertEqual(
            body["acting_chief"]["character_name"], "Faye Vaelent"
        )

    @override_settings(ALLIANCE_EXECUTOR_CHARACTER_ID=0)
    def test_no_executor_configured(self):
        body = self._group(self.freighters)
        self.assertTrue(body["chief_is_interim"])
        self.assertIsNone(body["acting_chief"])
        response = self._volunteer(self.pilot, self.supply, self.freighters)
        self.assertEqual(response.status_code, 503)

    def test_volunteer_dms_the_executor(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self._volunteer(
                self.pilot, self.pulse, self.fishermen, note="EU evenings"
            )
        self.assertEqual(response.status_code, 201, response.content)
        offer = TribeChiefVolunteer.objects.get()
        self.assertEqual(offer.tribe_group, self.fishermen)
        delivery_users = set(
            NotificationDelivery.objects.filter(
                notification_type=TRIBE_CHIEF_VOLUNTEERED_KEY
            ).values_list("user_id", flat=True)
        )
        self.assertEqual(delivery_users, {self.executor.pk})
        self.assertTrue(
            self._group(self.fishermen, self.pilot)["has_volunteered"]
        )

        again = self._volunteer(self.pilot, self.pulse, self.fishermen)
        self.assertEqual(again.status_code, 400)

    def test_cannot_volunteer_for_a_filled_seat(self):
        response = self._volunteer(self.pilot, self.pulse)
        self.assertEqual(response.status_code, 400)

    def test_dm_render_has_appoint_button(self):
        rendered = render_chief_volunteered(
            {
                "volunteer_id": 42,
                "pilot": "Casper Sullivan",
                "seat_name": "Fishermen",
                "tribe_name": "Pulse",
                "is_tribe_seat": False,
                "interim": "Faye Vaelent",
                "note": "EU evenings",
                "url": "https://example.test/x",
            }
        )
        self.assertIn("Faye Vaelent is interim", rendered["body"])
        buttons = rendered["discord_components"][0]["components"]
        self.assertEqual(buttons[0]["custom_id"], appoint_custom_id(42))
        self.assertEqual(buttons[2]["url"], "https://example.test/x")

    def test_only_the_executor_lists_and_appoints(self):
        self._volunteer(self.pilot, self.pulse, self.fishermen)
        offer = TribeChiefVolunteer.objects.get()
        url = (
            f"{BASE_URL}/{self.pulse.pk}/chief-volunteers"
            f"?tribe_group_id={self.fishermen.pk}"
        )
        self.assertEqual(
            self.client.get(url, **_auth(self.tribe_chief)).status_code, 403
        )
        listed = self.client.get(url, **_auth(self.executor)).json()
        self.assertEqual([row["id"] for row in listed], [offer.pk])
        self.assertEqual(listed[0]["character_name"], "Casper Sullivan")

        denied = self.client.post(
            f"{BASE_URL}/chief-volunteers/{offer.pk}/appoint",
            **_auth(self.tribe_chief),
        )
        self.assertEqual(denied.status_code, 403)

    @patch("tribes.helpers.chiefs._queue_dm_update")
    def test_appoint_group_chief_closes_other_offers(self, queue_dm):
        self._volunteer(self.pilot, self.pulse, self.fishermen)
        self._volunteer(self.other, self.pulse, self.fishermen)
        offer = TribeChiefVolunteer.objects.get(user=self.pilot)
        response = self.client.post(
            f"{BASE_URL}/chief-volunteers/{offer.pk}/appoint",
            **_auth(self.executor),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.fishermen.refresh_from_db()
        self.assertEqual(self.fishermen.chief, self.pilot)
        self.assertTrue(
            TribeGroupMembership.objects.filter(
                user=self.pilot,
                tribe_group=self.fishermen,
                status=TribeGroupMembership.STATUS_ACTIVE,
            ).exists()
        )
        statuses = dict(
            TribeChiefVolunteer.objects.values_list("user_id", "status")
        )
        self.assertEqual(statuses[self.pilot.pk], "appointed")
        self.assertEqual(statuses[self.other.pk], "closed")
        self.assertEqual(queue_dm.call_count, 2)
        self.assertFalse(self._group(self.fishermen)["chief_is_interim"])

    @patch("tribes.helpers.chiefs._queue_dm_update")
    def test_appoint_tribe_chief(self, queue_dm):
        self._volunteer(self.pilot, self.supply)
        offer = TribeChiefVolunteer.objects.get()
        self.assertIsNone(offer.tribe_group)
        response = self.client.post(
            f"{BASE_URL}/chief-volunteers/{offer.pk}/appoint",
            **_auth(self.executor),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.supply.refresh_from_db()
        self.assertEqual(self.supply.chief, self.pilot)
        queue_dm.assert_called_once()
        # The new tribe chief now stands in for its chiefless groups.
        group = ChiefResolver().for_group(self.freighters)
        self.assertEqual(group.user, self.pilot)
        self.assertTrue(group.is_interim)

    @patch("tribes.helpers.chiefs._queue_dm_update")
    def test_discord_buttons_check_the_clicker(self, queue_dm):
        bot = User.objects.create_superuser(username="bot")
        self._volunteer(self.pilot, self.pulse, self.fishermen)
        offer = TribeChiefVolunteer.objects.get()
        url = f"{BASE_URL}/chief-volunteers/{offer.pk}/discord-decline"
        wrong = self.client.post(
            url,
            data={"discord_user_id": 701},
            content_type="application/json",
            **_auth(bot),
        )
        self.assertEqual(wrong.status_code, 403)
        not_bot = self.client.post(
            url,
            data={"discord_user_id": 700},
            content_type="application/json",
            **_auth(self.pilot),
        )
        self.assertEqual(not_bot.status_code, 403)
        right = self.client.post(
            url,
            data={"discord_user_id": 700},
            content_type="application/json",
            **_auth(bot),
        )
        self.assertEqual(right.status_code, 200, right.content)
        offer.refresh_from_db()
        self.assertEqual(offer.status, "declined")
        queue_dm.assert_called_once()
        self.fishermen.refresh_from_db()
        self.assertIsNone(self.fishermen.chief)

    def test_appoint_edits_the_executor_dm(self):
        with self.captureOnCommitCallbacks(execute=True):
            self._volunteer(self.pilot, self.pulse, self.fishermen)
        offer = TribeChiefVolunteer.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"{BASE_URL}/chief-volunteers/{offer.pk}/appoint",
                **_auth(self.executor),
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.tasks_discord.update_message.assert_called_once()
        payload = self.tasks_discord.update_message.call_args.kwargs["payload"]
        self.assertEqual(payload["components"], [])
        self.assertEqual(
            payload["embeds"][0]["title"],
            "Casper Sullivan is now chief of Fishermen",
        )

    def test_failed_role_sync_rolls_the_appointment_back(self):
        # pylint: disable-next=import-outside-toplevel
        from discord.exceptions import DiscordRoleAssignmentError

        self._volunteer(self.pilot, self.pulse, self.fishermen)
        offer = TribeChiefVolunteer.objects.get()
        with patch(
            "tribes.helpers.chiefs._activate_membership",
            side_effect=DiscordRoleAssignmentError("no role"),
        ):
            response = self.client.post(
                f"{BASE_URL}/chief-volunteers/{offer.pk}/appoint",
                **_auth(self.executor),
            )
        self.assertEqual(response.status_code, 502)
        offer.refresh_from_db()
        self.assertEqual(offer.status, "pending")
        self.fishermen.refresh_from_db()
        self.assertIsNone(self.fishermen.chief)


@override_settings(ALLIANCE_EXECUTOR_CHARACTER_ID=EXECUTOR_CHARACTER_ID)
class InterimChiefPowersTestCase(TestCase):
    """An interim chief acts as chief: manages, gets applications."""

    def setUp(self):
        self.executor = _pilot("bear2", EXECUTOR_CHARACTER_ID, "BearThatCares")
        self.tribe_chief = _pilot("faye2", 93001, "Faye Vaelent")
        self.pilot = _pilot("casper2", 93002, "Casper Sullivan")
        self.pulse = Tribe.objects.create(
            name="Pulse", slug="pulse-powers", chief=self.tribe_chief
        )
        self.fishermen = TribeGroup.objects.create(
            tribe=self.pulse, name="Fishermen", code="pulse.fish-powers"
        )
        self.supply = Tribe.objects.create(name="Supply", slug="supply-pw")
        self.freighters = TribeGroup.objects.create(
            tribe=self.supply, name="Freighters", code="supply.frt-powers"
        )
        self.market = TribeGroup.objects.create(
            tribe=self.supply,
            name="Market",
            code="supply.mkt-powers",
            chief=self.pilot,
        )

    def test_executor_manages_a_chiefless_tribe(self):
        # pylint: disable-next=import-outside-toplevel
        from tribes.helpers.permissions import (
            user_can_manage_group,
            user_is_tribe_chief,
        )

        self.assertTrue(user_is_tribe_chief(self.executor, self.supply))
        self.assertTrue(user_can_manage_group(self.executor, self.freighters))
        # Like a tribe chief, every group in the tribe, chief or not.
        self.assertTrue(user_can_manage_group(self.executor, self.market))
        # Not a tribe that has its own chief.
        self.assertFalse(user_is_tribe_chief(self.executor, self.pulse))
        self.assertFalse(user_can_manage_group(self.executor, self.fishermen))
        self.assertFalse(user_can_manage_group(self.pilot, self.freighters))

    def test_executor_passes_tribe_chief_feature_gates(self):
        # pylint: disable-next=import-outside-toplevel
        from groups.helpers.feature_access import (
            _chief_tribe_group_ids,
            feature_batch,
        )

        with feature_batch(self.executor):
            led = _chief_tribe_group_ids(self.executor)
        self.assertIn(self.freighters.pk, led)
        self.assertIn(self.market.pk, led)
        self.assertNotIn(self.fishermen.pk, led)

    @override_settings(ALLIANCE_EXECUTOR_CHARACTER_ID=0)
    def test_no_executor_no_powers(self):
        # pylint: disable-next=import-outside-toplevel
        from tribes.helpers.permissions import user_can_manage_group

        self.assertFalse(user_can_manage_group(self.executor, self.freighters))

    def test_applications_notify_the_interim_chief(self):
        # pylint: disable-next=import-outside-toplevel
        from tribes.endpoints.memberships.post_membership import (
            _notify_chief_of_new_request,
        )

        cases = [
            (self.fishermen, self.tribe_chief),
            (self.freighters, self.executor),
            (self.market, self.pilot),
        ]
        for group, expected in cases:
            membership = TribeGroupMembership.objects.create(
                user=(
                    self.tribe_chief if expected is self.pilot else self.pilot
                ),
                tribe_group=group,
                status=TribeGroupMembership.STATUS_PENDING,
            )
            module = importlib.import_module(
                "tribes.endpoints.memberships.post_membership"
            )
            with patch.object(module, "notify_user") as notify:
                _notify_chief_of_new_request(membership)
            self.assertEqual(notify.call_args.args[0], expected, group.name)

    def test_executor_joins_the_tribe_chief_auth_group(self):
        # pylint: disable-next=import-outside-toplevel
        from groups.helpers import (
            TRIBE_CHIEF_GROUP_NAME,
            sync_tribe_chief_group_membership,
        )

        sync_tribe_chief_group_membership()
        chiefs = set(
            Group.objects.get(
                name=TRIBE_CHIEF_GROUP_NAME
            ).user_set.values_list("pk", flat=True)
        )
        self.assertIn(self.executor.pk, chiefs)
        self.assertIn(self.tribe_chief.pk, chiefs)


@override_settings(ALLIANCE_EXECUTOR_CHARACTER_ID=EXECUTOR_CHARACTER_ID)
class AppointRaceTestCase(TestCase):
    def setUp(self):
        self.executor = _pilot("bear3", EXECUTOR_CHARACTER_ID, "BearThatCares")
        self.first = _pilot("casper3", 94001, "Casper Sullivan")
        self.second = _pilot("zigg3", 94002, "Zigg Omelo")
        self.supply = Tribe.objects.create(name="Supply", slug="supply-race")

    @patch("tribes.helpers.chiefs._queue_dm_update")
    def test_stale_offer_cannot_appoint_a_second_chief(self, queue_dm):
        # pylint: disable-next=import-outside-toplevel
        from tribes.helpers.chiefs import ChiefVolunteerError, appoint

        first = TribeChiefVolunteer.objects.create(
            tribe=self.supply, user=self.first
        )
        second = TribeChiefVolunteer.objects.create(
            tribe=self.supply, user=self.second
        )
        # Both loaded before either click lands.
        stale = TribeChiefVolunteer.objects.get(pk=second.pk)
        appoint(first, self.executor)
        with self.assertRaises(ChiefVolunteerError):
            appoint(stale, self.executor)
        self.supply.refresh_from_db()
        self.assertEqual(self.supply.chief, self.first)
        self.assertEqual(queue_dm.call_count, 2)

    @patch("tribes.helpers.chiefs._queue_dm_update")
    @patch(
        "tribes.helpers.chief_membership."
        "ensure_tribe_chiefs_have_group_memberships",
        side_effect=RuntimeError("discord down"),
    )
    def test_membership_sync_failure_keeps_the_appointment(
        self, ensure, queue_dm
    ):
        # pylint: disable-next=import-outside-toplevel
        from tribes.helpers.chiefs import appoint

        offer = TribeChiefVolunteer.objects.create(
            tribe=self.supply, user=self.first
        )
        appoint(offer, self.executor)
        self.supply.refresh_from_db()
        self.assertEqual(self.supply.chief, self.first)
        ensure.assert_called_once()
        queue_dm.assert_called_once()
