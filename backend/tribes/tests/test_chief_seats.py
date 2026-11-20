"""A tribe group's timezone chief seats (US, EU, AU).

Every seated chief leads the group: they manage it, use tribe-chief
features (freight.manage, #3113), and get the group's pings. Pilots
volunteer for one seat; the executor appoints into that seat; superusers
fill or empty any seat.
"""

import importlib
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from app.testing import make_token
from eveonline.models import EveCharacter, EvePlayer
from groups.helpers import (
    TRIBE_CHIEF_GROUP_NAME,
    sync_tribe_chief_group_membership,
)
from groups.helpers.feature_access import can_use_feature, clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncFeatures,
)
from groups.models import PilotFeature
from timezones.models import PilotTimezone
from tribes.helpers import user_can_manage_group
from tribes.helpers.chief_regions import home_region, pick_region
from tribes.helpers.chiefs import (
    ChiefResolver,
    ChiefVolunteerError,
    appoint,
    set_chief,
    volunteer,
)
from tribes.models import (
    Tribe,
    TribeChiefVolunteer,
    TribeGroup,
    TribeGroupChief,
)

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
        group_post_save, sender=Group, dispatch_uid="group_post_save"
    )


def _pilot(username, character_id, home=None):
    user = User.objects.create_user(username=username)
    character = EveCharacter.objects.create(
        character_id=character_id, character_name=username.title(), user=user
    )
    EvePlayer.objects.create(
        user=user, primary_character=character, nickname=username
    )
    if home:
        PilotTimezone.objects.create(
            user=user,
            home=home,
            assessed_at=timezone.now(),
            changed_at=timezone.now(),
        )
    return user


class ChiefRegionTests(TestCase):
    def test_home_region_reads_home_then_brackets(self):
        self.assertEqual(home_region("EU", ["USTZ"]), "EU")
        self.assertEqual(home_region(None, ["AUTZ+"]), "AU")
        self.assertIsNone(home_region("", []))

    def test_pick_region_prefers_free_own_seat(self):
        self.assertEqual(pick_region("EU", set()), "EU")
        self.assertEqual(pick_region("EU", {"EU"}), "US")
        self.assertEqual(pick_region(None, {"US"}), "EU")
        self.assertIsNone(pick_region("AU", {"US", "EU", "AU"}))


@override_settings(ALLIANCE_EXECUTOR_CHARACTER_ID=EXECUTOR_CHARACTER_ID)
class ChiefSeatTests(TestCase):
    def setUp(self):
        notify = patch("tribes.helpers.chiefs.notify_user")
        self.notify = notify.start()
        self.addCleanup(notify.stop)
        dm = patch("tribes.helpers.chiefs._queue_dm_update")
        dm.start()
        self.addCleanup(dm.stop)

        self.executor = _pilot("bear", EXECUTOR_CHARACTER_ID)
        self.us_chief = _pilot("usa", 93001, home="US")
        self.eu_chief = _pilot("euro", 93002, home="EU")
        self.au_pilot = _pilot("aussie", 93003, home="AU")
        self.eu_pilot = _pilot("berlin", 93004, home="EU")
        self.member = _pilot("member", 93005)
        self.superuser = User.objects.create_superuser(username="root")
        self.tribe = Tribe.objects.create(name="Supply", slug="supply-seats")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe, name="Freighters", code="supply.seats"
        )
        TribeGroupChief.objects.create(
            tribe_group=self.group, region="US", user=self.us_chief
        )
        TribeGroupChief.objects.create(
            tribe_group=self.group, region="EU", user=self.eu_chief
        )

    def _regions(self):
        return dict(
            TribeGroupChief.objects.filter(tribe_group=self.group).values_list(
                "region", "user_id"
            )
        )

    def test_every_seated_chief_manages_the_group(self):
        self.assertTrue(user_can_manage_group(self.us_chief, self.group))
        self.assertTrue(user_can_manage_group(self.eu_chief, self.group))
        self.assertFalse(user_can_manage_group(self.member, self.group))

    def test_every_seated_chief_gets_freight_manage(self):
        SyncFeatures().handle()
        feature = PilotFeature.objects.get(code="freight.manage")
        feature.tribe_groups.set([self.group])
        clear_feature_cache()
        self.addCleanup(clear_feature_cache)

        self.assertTrue(can_use_feature(self.us_chief, "freight.manage"))
        self.assertTrue(can_use_feature(self.eu_chief, "freight.manage"))
        self.assertFalse(can_use_feature(self.member, "freight.manage"))

    def test_resolver_lists_every_chief_in_seat_order(self):
        acting = ChiefResolver().for_group(self.group)
        self.assertFalse(acting.is_interim)
        self.assertEqual(acting.user, self.us_chief)
        self.assertEqual(acting.users, (self.us_chief, self.eu_chief))

    def test_group_with_no_seats_is_led_by_the_tribe_chief(self):
        self.tribe.chief = self.member
        self.tribe.save()
        TribeGroupChief.objects.filter(tribe_group=self.group).delete()
        acting = ChiefResolver().for_group(self.group)
        self.assertTrue(acting.is_interim)
        self.assertEqual(acting.users, (self.member,))

    def test_tribe_chief_group_includes_every_seat(self):
        sync_tribe_chief_group_membership()
        chiefs = set(
            Group.objects.get(
                name=TRIBE_CHIEF_GROUP_NAME
            ).user_set.values_list("pk", flat=True)
        )
        self.assertTrue({self.us_chief.pk, self.eu_chief.pk} <= chiefs)

    def test_application_notifies_every_chief(self):
        # The package re-exports a function named like the module.
        module = importlib.import_module(
            "tribes.endpoints.memberships.post_membership"
        )
        membership = self.group.memberships.create(user=self.member)
        with patch.object(module, "notify_user") as notify:
            # pylint: disable-next=protected-access
            module._notify_chief_of_new_request(membership)
        notified = {call.args[0] for call in notify.call_args_list}
        self.assertEqual(notified, {self.us_chief, self.eu_chief})

    def test_volunteer_takes_their_own_open_seat(self):
        offer = volunteer(self.au_pilot, self.tribe, self.group)
        self.assertEqual(offer.region, "AU")

    def test_volunteer_falls_back_to_a_free_seat(self):
        offer = volunteer(self.eu_pilot, self.tribe, self.group)
        self.assertEqual(offer.region, "AU")

    def test_volunteer_cannot_pick_a_filled_seat(self):
        with self.assertRaises(ChiefVolunteerError):
            volunteer(self.au_pilot, self.tribe, self.group, region="EU")

    def test_a_chief_cannot_volunteer_for_another_seat(self):
        with self.assertRaises(ChiefVolunteerError):
            volunteer(self.us_chief, self.tribe, self.group, region="AU")

    def test_full_group_takes_no_volunteers(self):
        TribeGroupChief.objects.create(
            tribe_group=self.group, region="AU", user=self.au_pilot
        )
        with self.assertRaises(ChiefVolunteerError):
            volunteer(self.eu_pilot, self.tribe, self.group)

    def test_appoint_fills_the_offers_seat_and_keeps_the_others(self):
        TribeGroupChief.objects.filter(region="EU").delete()
        au_offer = volunteer(self.au_pilot, self.tribe, self.group)
        eu_offer = volunteer(self.eu_pilot, self.tribe, self.group)
        self.assertEqual((au_offer.region, eu_offer.region), ("AU", "EU"))

        appoint(au_offer, self.executor)

        self.assertEqual(self._regions()["AU"], self.au_pilot.pk)
        eu_offer.refresh_from_db()
        self.assertEqual(eu_offer.status, TribeChiefVolunteer.STATUS_PENDING)
        self.assertTrue(
            self.group.memberships.filter(
                user=self.au_pilot, status="active"
            ).exists()
        )

    def test_superuser_fills_a_seat_by_region(self):
        set_chief(
            self.superuser, self.tribe, self.group, self.au_pilot, region="AU"
        )
        self.assertEqual(self._regions()["AU"], self.au_pilot.pk)

    def test_superuser_moves_a_chief_to_another_seat(self):
        set_chief(
            self.superuser, self.tribe, self.group, self.eu_chief, region="AU"
        )
        self.assertEqual(
            self._regions(), {"US": self.us_chief.pk, "AU": self.eu_chief.pk}
        )

    def test_superuser_empties_one_seat(self):
        set_chief(self.superuser, self.tribe, self.group, None, region="US")
        self.assertEqual(self._regions(), {"EU": self.eu_chief.pk})

    def test_emptying_a_group_seat_needs_a_region(self):
        with self.assertRaises(ChiefVolunteerError):
            set_chief(self.superuser, self.tribe, self.group, None)


@override_settings(ALLIANCE_EXECUTOR_CHARACTER_ID=EXECUTOR_CHARACTER_ID)
class ChiefSeatApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.us_chief = _pilot("usa", 94001, home="US")
        self.au_chief = _pilot("aussie", 94002, home="AU")
        self.superuser = User.objects.create_superuser(username="root")
        self.tribe = Tribe.objects.create(name="Capitals", slug="cap-seats")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads", code="capitals.seat-dreads"
        )
        TribeGroupChief.objects.create(
            tribe_group=self.group, region="US", user=self.us_chief
        )
        TribeGroupChief.objects.create(
            tribe_group=self.group, region="AU", user=self.au_chief
        )

    def test_group_lists_all_three_seats(self):
        response = self.client.get(
            f"/api/tribes/{self.tribe.pk}/groups/{self.group.pk}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["chief"]["character_id"], 94001)
        self.assertFalse(body["chief_is_interim"])
        seats = {seat["region"]: seat for seat in body["chiefs"]}
        self.assertEqual(list(seats), ["US", "EU", "AU"])
        self.assertEqual(seats["AU"]["chief"]["character_id"], 94002)
        self.assertEqual(seats["AU"]["label"], "AUTZ")
        self.assertTrue(seats["EU"]["is_open"])
        self.assertIsNone(seats["EU"]["chief"])

    def test_superuser_sets_a_seat_over_the_api(self):
        pilot = _pilot("berlin", 94003)
        response = self.client.put(
            f"/api/tribes/{self.tribe.pk}/groups/{self.group.pk}/chief",
            data={"user_id": pilot.pk, "region": "EU"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {make_token(self.superuser)}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["region"], "EU")
        self.assertTrue(
            TribeGroupChief.objects.filter(
                tribe_group=self.group, region="EU", user=pilot
            ).exists()
        )
