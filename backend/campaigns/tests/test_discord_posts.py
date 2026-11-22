"""The campaign bot's Discord posts: intel, timerboard, schedule, pings,
relays to coordinators' servers, and the coordinator invite DM."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from requests import HTTPError, Response

from campaigns.models import (
    CampaignCoordinator,
    CampaignDiscordBoard,
    CampaignDiscordLink,
    CampaignKind,
    CampaignParty,
    CampaignStatus,
    PartySide,
)
from campaigns.services import coordinators, discord_posts
from campaigns.services import structures as structure_service
from campaigns.tests.helpers import make_campaign
from eveonline.models import EveCharacter
from fleets.models import EveFleet
from notifications.models import NotificationDelivery
from structures.models import EveStructureTimer

OURS_INTEL = 101
OURS_TIMERS = 102
OURS_SCHEDULE = 103
OURS_PINGS = 104
THEIR_INTEL = 201
THEIR_TIMERS = 202
THEIR_PINGS = 204


def _sent(queue):
    """{channel_id: [payload, ...]} from queue_channel_message calls."""
    out = {}
    for call in queue.call_args_list:
        out.setdefault(call.args[0], []).append(call.kwargs["payload"])
    return out


class CampaignDiscordTestCase(TestCase):
    def setUp(self):
        self.campaign = make_campaign(
            kind=CampaignKind.STRATEGIC,
            coordination_intel_channel_id=OURS_INTEL,
            coordination_timers_channel_id=OURS_TIMERS,
            coordination_schedule_channel_id=OURS_SCHEDULE,
            coordination_fleets_channel_id=OURS_PINGS,
        )
        CampaignParty.objects.create(
            campaign=self.campaign,
            side=PartySide.ENEMY,
            alliance_id=99000001,
            name="Enemy Alliance",
        )
        self.link = CampaignDiscordLink.objects.create(
            campaign=self.campaign,
            guild_id=555,
            guild_name="Allies",
            intel_channel_id=THEIR_INTEL,
            timers_channel_id=THEIR_TIMERS,
            fleets_channel_id=THEIR_PINGS,
        )
        patcher = patch("discord.outbox.queue_channel_message")
        self.queue = patcher.start()
        self.addCleanup(patcher.stop)
        refresh = patch("campaigns.services.discord_posts.queue_board_refresh")
        self.refresh = refresh.start()
        self.addCleanup(refresh.stop)

    def _timer(self, hours=5, **fields):
        defaults = {
            "name": "Enemy Fort",
            "type": "fortizar",
            "state": "armor",
            "timer": timezone.now() + timedelta(hours=hours),
            "system_name": "Kamela",
            "alliance_name": "Enemy Alliance",
        }
        defaults.update(fields)
        return EveStructureTimer.objects.create(**defaults)

    # --- intel ----------------------------------------------------------

    def test_new_structure_posts_unpinged_intel_to_ours_and_relay(self):
        with self.captureOnCommitCallbacks(execute=True):
            structure_service.attach_structure(
                self.campaign,
                name="Enemy Astra",
                structure_type="astrahus",
                system_name="Kamela",
                alliance_name="Enemy Alliance",
                alliance_id=99000001,
            )
        sent = _sent(self.queue)
        self.assertEqual(set(sent), {OURS_INTEL, THEIR_INTEL})
        payload = sent[OURS_INTEL][0]
        self.assertNotIn("content", payload)
        self.assertEqual(payload["allowed_mentions"], {"parse": []})
        embed = payload["embeds"][0]
        self.assertEqual(embed["title"], "Astrahus · Enemy Astra")
        self.assertIn("New structure", embed["description"])
        self.assertIn("/types/35832/render", embed["thumbnail"]["url"])
        self.assertIn("/alliances/99000001/logo", embed["author"]["icon_url"])
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        self.assertEqual(fields["Side"], "Enemy")
        self.assertEqual(fields["System"], "Kamela")
        self.assertEqual(fields["Alliance"], "Enemy Alliance")

    def test_updating_a_known_structure_posts_nothing(self):
        kwargs = {
            "name": "Enemy Astra",
            "structure_type": "astrahus",
            "system_name": "Kamela",
        }
        structure_service.attach_structure(self.campaign, **kwargs)
        self.queue.reset_mock()
        structure_service.attach_structure(
            self.campaign, fitting="[Astrahus]", **kwargs
        )
        self.queue.assert_not_called()

    def test_new_timer_posts_one_timer_line_not_a_structure_line(self):
        timer = self._timer()
        structure_service.attach_timer(self.campaign, timer)
        sent = _sent(self.queue)
        self.assertEqual(set(sent), {OURS_INTEL, THEIR_INTEL})
        self.assertEqual(len(sent[OURS_INTEL]), 1)
        embed = sent[OURS_INTEL][0]["embeds"][0]
        self.assertIn("New timer", embed["description"])
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        self.assertIn("Armor", fields["Timer"])
        self.assertIn(f"<t:{int(timer.timer.timestamp())}:R>", fields["Timer"])
        self.assertIn("/types/35833/render", embed["thumbnail"]["url"])
        self.refresh.assert_called_with(self.campaign.id, "timers")

    def test_relinking_the_same_timer_does_not_post_again(self):
        timer = self._timer()
        structure_service.attach_timer(self.campaign, timer)
        self.queue.reset_mock()
        structure_service.attach_timer(self.campaign, timer)
        self.queue.assert_not_called()

    def test_relay_only_gets_what_coordinators_may_see(self):
        self.campaign.coordinator_scopes = ["sides", "structures"]
        self.campaign.save(update_fields=["coordinator_scopes"])
        structure_service.attach_timer(self.campaign, self._timer())
        self.assertEqual(set(_sent(self.queue)), {OURS_INTEL})

    def test_finished_campaign_posts_nothing(self):
        self.campaign.status = CampaignStatus.COMPLETED
        self.campaign.save(update_fields=["status"])
        structure_service.attach_timer(self.campaign, self._timer())
        self.queue.assert_not_called()

    # --- fleet pings ----------------------------------------------------

    def _fleet(self, **fields):
        defaults = {
            "type": "strategic",
            "start_time": timezone.now() + timedelta(hours=2),
            "campaign": self.campaign,
            "status": "pending",
            "objective": "Hit the fort",
        }
        defaults.update(fields)
        with patch("fleets.signals.queue_fleet_schedule_refresh"):
            return EveFleet.objects.create(**defaults)

    def _start(self, fleet):
        with patch("fleets.signals.queue_fleet_schedule_refresh"):
            fleet.status = "active"
            fleet.save()

    def test_fleet_starting_pings_everyone_once(self):
        fleet = self._fleet()
        self.queue.reset_mock()
        self._start(fleet)
        sent = _sent(self.queue)
        self.assertEqual(set(sent), {OURS_PINGS, THEIR_PINGS})
        ours = sent[OURS_PINGS][0]
        self.assertEqual(ours["content"], "@everyone")
        self.assertEqual(ours["allowed_mentions"], {"parse": ["everyone"]})
        embed = ours["embeds"][0]
        self.assertEqual(embed["title"], "INCOMING PING TRANSMISSION...")
        self.assertIn("**AUDIENCE**: TEST PUSH", embed["description"])
        self.assertIn("Hit the fort", embed["description"])

        def info_url(payload):
            buttons = payload["components"][0]["components"]
            return next(
                b["url"]
                for b in buttons
                if b["label"] == "View Fleet Information"
            )

        self.assertIn("/fleets/", info_url(ours))
        self.assertIn(
            f"/campaigns/{self.campaign.slug}/",
            info_url(sent[THEIR_PINGS][0]),
        )

        self.queue.reset_mock()
        with patch("fleets.signals.queue_fleet_schedule_refresh"):
            fleet.description = "edited"
            fleet.save()
        self.queue.assert_not_called()

    def test_private_fleet_never_pings(self):
        fleet = self._fleet(invite_only=True)
        self.queue.reset_mock()
        self._start(fleet)
        self.queue.assert_not_called()

    def test_fleet_save_refreshes_old_and_new_schedule(self):
        other = make_campaign(
            slug="other",
            short_code="OTH",
            coordination_schedule_channel_id=OURS_SCHEDULE + 1,
        )
        fleet = self._fleet()
        self.refresh.reset_mock()
        with patch("fleets.signals.queue_fleet_schedule_refresh"):
            fleet.campaign = other
            fleet.save()
        refreshed = {call.args for call in self.refresh.call_args_list}
        self.assertEqual(
            refreshed,
            {(self.campaign.id, "schedule"), (other.id, "schedule")},
        )


@override_settings(DISCORD_FLEET_EMOJIS={})
class BoardTestCase(TestCase):
    def setUp(self):
        self.campaign = make_campaign(
            kind=CampaignKind.STRATEGIC,
            coordination_timers_channel_id=OURS_TIMERS,
            coordination_schedule_channel_id=OURS_SCHEDULE,
        )
        CampaignParty.objects.create(
            campaign=self.campaign,
            side=PartySide.ALLY,
            alliance_id=99000002,
            name="Friend Alliance",
        )
        self.client = MagicMock()
        self.client.create_message.return_value.json.return_value = {
            "id": "900"
        }
        patcher = patch("discord.outbox.queue_channel_message")
        patcher.start()
        self.addCleanup(patcher.stop)
        refresh = patch("campaigns.services.discord_posts.queue_board_refresh")
        refresh.start()
        self.addCleanup(refresh.stop)

    def test_timerboard_groups_friendly_and_other_and_hides_past(self):
        now = timezone.now()
        friendly = EveStructureTimer.objects.create(
            name="Our Raitaru",
            type="raitaru",
            state="hull",
            timer=now + timedelta(hours=3),
            system_name="Kamela",
        )
        structure_service.attach_timer(self.campaign, friendly)
        structure = self.campaign.structures.get(timer=friendly)
        structure.alliance_id = 99000002
        structure.save(update_fields=["alliance_id"])
        EveStructureTimer.objects.create(
            name="Loose timer",
            type="astrahus",
            state="armor",
            timer=now + timedelta(hours=6),
            system_name="Kamela",
            campaign=self.campaign,
        )
        EveStructureTimer.objects.create(
            name="Old timer",
            type="astrahus",
            state="armor",
            timer=now - timedelta(hours=1),
            system_name="Kamela",
            campaign=self.campaign,
        )
        content = discord_posts.timerboard(self.campaign)["content"]
        self.assertIn("### Friendly timers", content)
        self.assertIn("Our Raitaru", content)
        self.assertIn("(final)", content)
        self.assertIn("### Other timers", content)
        self.assertIn("Loose timer", content)
        self.assertNotIn("Old timer", content)
        self.assertNotIn("Enemy timers", content)

    def test_board_posts_once_then_edits_only_on_change(self):
        discord_posts.refresh_board(self.campaign, "timers", self.client)
        self.client.create_message.assert_called_once()
        board = CampaignDiscordBoard.objects.get(kind="timers")
        self.assertEqual(board.message_id, 900)

        self.client.reset_mock()
        discord_posts.refresh_board(self.campaign, "timers", self.client)
        self.client.update_message.assert_not_called()
        self.client.create_message.assert_not_called()

        EveStructureTimer.objects.create(
            name="New timer",
            type="astrahus",
            state="armor",
            timer=timezone.now() + timedelta(hours=1),
            system_name="Kamela",
            campaign=self.campaign,
        )
        discord_posts.refresh_board(self.campaign, "timers", self.client)
        self.client.update_message.assert_called_once()
        self.assertEqual(self.client.update_message.call_args.args[1], 900)

    def test_deleted_board_message_is_posted_again(self):
        discord_posts.refresh_board(self.campaign, "timers", self.client)
        EveStructureTimer.objects.create(
            name="New timer",
            type="astrahus",
            state="armor",
            timer=timezone.now() + timedelta(hours=1),
            system_name="Kamela",
            campaign=self.campaign,
        )
        response = Response()
        response.status_code = 404
        self.client.update_message.side_effect = HTTPError(response=response)
        self.client.create_message.return_value.json.return_value = {
            "id": "901"
        }
        discord_posts.refresh_board(self.campaign, "timers", self.client)
        self.assertEqual(
            CampaignDiscordBoard.objects.get(kind="timers").message_id, 901
        )

    def test_unpicked_channel_loses_its_board(self):
        discord_posts.refresh_board(self.campaign, "timers", self.client)
        self.campaign.coordination_timers_channel_id = None
        self.campaign.save(update_fields=["coordination_timers_channel_id"])
        discord_posts.refresh_board(self.campaign, "timers", self.client)
        self.client.delete_message.assert_called_once_with(OURS_TIMERS, 900)
        self.assertFalse(CampaignDiscordBoard.objects.exists())

    def test_schedule_lists_campaign_formups_only(self):
        start = timezone.now() + timedelta(hours=4)
        with patch("fleets.signals.queue_fleet_schedule_refresh"):
            EveFleet.objects.create(
                type="strategic",
                start_time=start,
                campaign=self.campaign,
                objective="Hit the fort",
            )
            EveFleet.objects.create(
                type="strategic",
                start_time=start,
                campaign=self.campaign,
                invite_only=True,
                objective="Secret",
            )
            EveFleet.objects.create(
                type="standing", start_time=start, campaign=self.campaign
            )
            EveFleet.objects.create(
                type="strategic",
                start_time=start,
                campaign=self.campaign,
                status="cancelled",
                objective="Called off",
            )
            EveFleet.objects.create(
                type="strategic", start_time=start, objective="Not ours"
            )
        content = discord_posts.schedule(self.campaign)["content"]
        self.assertTrue(content.startswith("## Fleet Schedule · Test Push"))
        self.assertIn("Hit the fort", content)
        self.assertIn(f"(<t:{int(start.timestamp())}>)", content)
        self.assertIn("**No Location**", content)
        for hidden in ("Secret", "Standing", "Called off", "Not ours"):
            self.assertNotIn(hidden, content)

    def test_empty_schedule_says_so(self):
        content = discord_posts.schedule(self.campaign)["content"]
        self.assertIn("No upcoming fleets", content)

    def test_long_board_fits_one_message(self):
        now = timezone.now()
        for index in range(80):
            EveStructureTimer.objects.create(
                name=f"Timer number {index} with a long name",
                type="astrahus",
                state="armor",
                timer=now + timedelta(hours=index + 1),
                system_name="Kamela",
                campaign=self.campaign,
            )
        content = discord_posts.timerboard(self.campaign)["content"]
        self.assertLessEqual(len(content), 2000)
        self.assertIn("more", content)


class CoordinatorInviteDmTestCase(TestCase):
    def setUp(self):
        self.campaign = make_campaign()
        self.inviter = User.objects.create(username="director")
        self.owner = User.objects.create(username="coordinator")

    def _coordinator(self):
        return CampaignCoordinator.objects.create(
            campaign=self.campaign,
            character_id=7001,
            character_name="Outside Pilot",
            invited_by=self.inviter,
        )

    def _deliveries(self):
        return NotificationDelivery.objects.filter(
            user=self.owner, notification_type="campaigns.coordinator_invited"
        )

    def test_owned_character_is_messaged_once(self):
        EveCharacter.objects.create(
            character_id=7001, character_name="Outside Pilot", user=self.owner
        )
        coordinator = self._coordinator()
        with patch("notifications.service._enqueue_delivery"):
            self.assertTrue(coordinators.notify(coordinator))
            self.assertFalse(coordinators.notify(coordinator))
        delivery = self._deliveries().get(channel="discord")
        self.assertIn(
            f"/campaigns/{self.campaign.slug}/", delivery.payload["url"]
        )
        self.assertIn("Outside Pilot", str(delivery.payload))

    def test_character_signing_in_later_gets_the_dm(self):
        coordinator = self._coordinator()
        with patch("notifications.service._enqueue_delivery"):
            self.assertFalse(coordinators.notify(coordinator))
            self.assertFalse(self._deliveries().exists())
            EveCharacter.objects.create(
                character_id=7001,
                character_name="Outside Pilot",
                user=self.owner,
            )
        self.assertTrue(self._deliveries().exists())
        coordinator.refresh_from_db()
        self.assertIsNotNone(coordinator.invite_notified_at)
