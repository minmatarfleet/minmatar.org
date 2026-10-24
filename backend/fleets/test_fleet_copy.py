"""Copy this fleet: POST /fleets/{id}/copy, can_copy and the in-game fits."""

from datetime import timedelta
from unittest.mock import patch

from django.db.models import signals
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from app.testing import make_token
from campaigns.models import CampaignStatus
from campaigns.tests.helpers import make_campaign
from eveonline.models import EveLocation
from fittings.models import EveDoctrine, EveFitting
from fleets.helpers.copy_fleet import (
    NOT_COPIED_CAMPAIGN,
    NOT_COPIED_LOCATION,
    NOT_COPIED_OPEN_TO_ALLIANCE,
    fits_to_save,
    save_copied_fits,
)
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetFitting,
    EveFleetFittingRefit,
    EveFleetRoleVolunteer,
    EveFleetShipVolunteer,
)
from fleets.tasks import queue_save_copied_fleet_fits
from fleets.tests import setup_fleet_reference_data
from tribes.models import TribeGroup
from tribes.tests.publishing_fixtures import (
    add_member,
    make_tribe_group,
    make_user,
)

BASE_URL = "/api/fleets"
VIEW = ("view_evefleet",)
FC_PERMS = ("view_evefleet", "add_evefleet")

MANUAL_EFT = "[Sabre, Sabre tackle]\nDamage Control II\n"
REFIT_EFT = "[Hurricane, Hurricane refit]\nDamage Control II\n"


def setUpModule():
    signals.post_save.disconnect(
        sender=EveFleet, dispatch_uid="update_fleet_schedule_on_save"
    )


def tearDownModule():
    # pylint: disable-next=import-outside-toplevel
    from fleets.signals import update_fleet_schedule_on_save

    signals.post_save.connect(
        update_fleet_schedule_on_save,
        sender=EveFleet,
        dispatch_uid="update_fleet_schedule_on_save",
    )


class FleetCopyTestBase(TestCase):
    def setUp(self):
        super().setUp()
        setup_fleet_reference_data()
        self.audience = EveFleetAudience.objects.get(name="Test Audience")
        self.staging = EveLocation.objects.get(location_id=123)
        self.fc = make_user("fc", perms=FC_PERMS, character_name="Mr FC")
        self.pilot = make_user("pilot", perms=VIEW)
        self.doctrine = EveDoctrine.objects.create(
            name="Tyfighters", type="non_strategic", description=""
        )
        self.next_week = timezone.now() + timedelta(days=7)

    def call(self, method, path, user, data=None):
        kwargs = {"HTTP_AUTHORIZATION": f"Bearer {make_token(user)}"}
        if data is not None:
            kwargs["data"] = data
            kwargs["content_type"] = "application/json"
        return getattr(Client(), method)(f"{BASE_URL}{path}", **kwargs)

    def copy(self, fleet, user, start_time=None):
        start_time = start_time or self.next_week
        return self.call(
            "post",
            f"/{fleet.id}/copy",
            user,
            {"start_time": start_time.isoformat()},
        )

    def fleet(self, **fields) -> EveFleet:
        values = {
            "type": "non_strategic",
            "description": "Form up in Amamake. Comms on Mumble.",
            "objective": "Tuesday Hed plex gang",
            "start_time": timezone.now() - timedelta(days=3),
            "created_by": self.fc,
            "audience": self.audience,
            "location": self.staging,
            "doctrine": self.doctrine,
            "disable_motd": True,
            "hide_volunteers": False,
            "status": "complete",
        }
        values.update(fields)
        return EveFleet.objects.create(**values)


class FleetCopyTests(FleetCopyTestBase):
    def test_copy_carries_every_fc_setting(self):
        campaign = make_campaign()
        source = self.fleet(campaign=campaign)

        response = self.copy(source, self.fc)

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["copied_from"], source.id)
        self.assertEqual(body["not_copied"], [])
        copy = EveFleet.objects.get(id=body["id"])
        self.assertNotEqual(copy.id, source.id)
        self.assertEqual(copy.type, "non_strategic")
        self.assertEqual(copy.description, source.description)
        self.assertEqual(copy.objective, "Tuesday Hed plex gang")
        self.assertEqual(copy.audience, self.audience)
        self.assertEqual(copy.location, self.staging)
        self.assertEqual(copy.doctrine, self.doctrine)
        self.assertEqual(copy.campaign, campaign)
        self.assertTrue(copy.disable_motd)
        self.assertFalse(copy.hide_volunteers)
        self.assertEqual(copy.created_by, self.fc)
        self.assertEqual(copy.status, "pending")
        self.assertEqual(copy.start_time, self.next_week)
        self.assertIsNone(copy.aar_link)
        self.assertIsNone(copy.host_group)

    def test_copy_keeps_the_original_unchanged(self):
        source = self.fleet(aar_link="https://discord.com/channels/1/2")
        before = EveFleet.objects.filter(id=source.id).values().get()

        self.copy(source, self.fc)

        self.assertEqual(
            EveFleet.objects.filter(id=source.id).values().get(), before
        )

    def test_copy_copies_added_ships_and_refits_not_signups(self):
        source = self.fleet(doctrine=None)
        catalog = EveFitting.objects.create(
            name="Scimitar [FL33T]",
            ship_id=11978,
            description="",
            eft_format="",
        )
        hull = EveFitting.objects.create(
            name="Hurricane [FL33T]",
            ship_id=24702,
            description="",
            eft_format=REFIT_EFT,
        )
        catalog_fit = EveFleetFitting.objects.create(
            eve_fleet=source,
            fitting=catalog,
            name=catalog.name,
            ship_id=catalog.ship_id,
            role="support",
            order=0,
        )
        manual_fit = EveFleetFitting.objects.create(
            eve_fleet=source,
            name="Sabre tackle",
            ship_id=22456,
            eft_format=MANUAL_EFT,
            role="utility",
            order=1,
            esi_fitting_id=555,
            esi_character_id=1,
        )
        EveFleetFittingRefit.objects.create(
            eve_fleet=source,
            fleet_fitting=manual_fit,
            name="Long point",
            cargo_modules="Warp Disruptor II x1",
            notes="Scram → point",
            eft_format=MANUAL_EFT,
            esi_fitting_id=556,
            esi_character_id=1,
        )
        EveFleetFittingRefit.objects.create(
            eve_fleet=source,
            fitting=hull,
            name="Armor",
            cargo_modules="1600mm Steel Plates II x1",
            eft_format=REFIT_EFT,
        )
        EveFleetShipVolunteer.objects.create(
            eve_fleet=source,
            character_id=99,
            character_name="Pilot",
            fleet_fitting=catalog_fit,
        )
        EveFleetRoleVolunteer.objects.create(
            eve_fleet=source,
            character_id=99,
            character_name="Pilot",
            role=EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR,
        )

        with patch("fleets.tasks.on_commit_enqueue"):
            response = self.copy(source, self.fc)

        self.assertEqual(response.status_code, 200, response.content)
        copy = EveFleet.objects.get(id=response.json()["id"])
        fits = list(
            EveFleetFitting.objects.filter(eve_fleet=copy).order_by("order")
        )
        self.assertEqual(
            [(f.fitting_id, f.name, f.ship_id, f.role, f.order) for f in fits],
            [
                (catalog.id, catalog.name, 11978, "support", 0),
                (None, "Sabre tackle", 22456, "utility", 1),
            ],
        )
        self.assertEqual(fits[1].eft_format, MANUAL_EFT)
        # The in-game fits belong to the old fleet.
        self.assertIsNone(fits[1].esi_fitting_id)
        self.assertIsNone(fits[1].esi_character_id)

        refits = {
            r.name: r
            for r in EveFleetFittingRefit.objects.filter(eve_fleet=copy)
        }
        self.assertEqual(set(refits), {"Long point", "Armor"})
        self.assertEqual(refits["Long point"].fleet_fitting, fits[1])
        self.assertEqual(
            refits["Long point"].cargo_modules, "Warp Disruptor II x1"
        )
        self.assertEqual(refits["Long point"].notes, "Scram → point")
        self.assertIsNone(refits["Long point"].esi_fitting_id)
        self.assertEqual(refits["Armor"].fitting, hull)
        self.assertIsNone(refits["Armor"].fleet_fitting)

        self.assertFalse(
            EveFleetShipVolunteer.objects.filter(eve_fleet=copy).exists()
        )
        self.assertFalse(
            EveFleetRoleVolunteer.objects.filter(eve_fleet=copy).exists()
        )
        # The original keeps its ships and sign-ups.
        self.assertEqual(
            EveFleetFitting.objects.filter(eve_fleet=source).count(), 2
        )
        self.assertEqual(
            EveFleetShipVolunteer.objects.filter(eve_fleet=source).count(), 1
        )

    def test_copy_of_an_upcoming_fleet(self):
        source = self.fleet(
            status="pending", start_time=timezone.now() + timedelta(hours=2)
        )

        response = self.copy(source, self.fc)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(EveFleet.objects.count(), 2)

    def test_start_time_must_be_in_the_future(self):
        source = self.fleet()

        response = self.copy(
            source, self.fc, timezone.now() - timedelta(minutes=1)
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"], "Pick a start time after now"
        )
        self.assertEqual(EveFleet.objects.count(), 1)

    def test_missing_fleet_is_404(self):
        response = self.call(
            "post",
            "/999999/copy",
            self.fc,
            {"start_time": self.next_week.isoformat()},
        )
        self.assertEqual(response.status_code, 404)

    def test_pilot_cannot_copy(self):
        source = self.fleet()

        response = self.copy(source, self.pilot)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(EveFleet.objects.count(), 1)

    def test_another_fc_cannot_copy(self):
        other_fc = make_user("other_fc", perms=FC_PERMS)
        source = self.fleet()

        response = self.copy(source, other_fc)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"], "Only this fleet's FC may copy it"
        )

    def test_fc_who_can_no_longer_schedule_cannot_copy(self):
        former_fc = make_user("former_fc", perms=VIEW)
        source = self.fleet(created_by=former_fc)

        response = self.copy(source, former_fc)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(EveFleet.objects.count(), 1)

    def test_strategic_fc_copies_another_fcs_fleet_and_leads_it(self):
        strategic = make_user(
            "strategic",
            perms=(*FC_PERMS, "manage_any_fleet"),
            character_name="Strategic FC",
        )
        source = self.fleet()

        response = self.copy(source, strategic)

        self.assertEqual(response.status_code, 200, response.content)
        copy = EveFleet.objects.get(id=response.json()["id"])
        self.assertEqual(copy.created_by, strategic)
        self.assertEqual(response.json()["fleet_commander"], strategic.id)
        source.refresh_from_db()
        self.assertEqual(source.created_by, self.fc)

    def test_campaign_fleets_cannot_be_copied(self):
        source = self.fleet(type="standing")

        response = self.copy(source, self.fc)

        self.assertEqual(response.status_code, 400)

    def test_ended_campaign_is_left_off(self):
        ended = make_campaign(
            slug="ended", short_code="END", status=CampaignStatus.COMPLETED
        )
        source = self.fleet(campaign=ended)

        response = self.copy(source, self.fc)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["not_copied"], [NOT_COPIED_CAMPAIGN])
        self.assertIsNone(
            EveFleet.objects.get(id=response.json()["id"]).campaign
        )

    def test_campaign_ending_before_the_new_date_is_left_off(self):
        campaign = make_campaign(end_at=timezone.now() + timedelta(days=2))
        source = self.fleet(campaign=campaign)

        response = self.copy(source, self.fc)

        self.assertEqual(response.json()["not_copied"], [NOT_COPIED_CAMPAIGN])
        self.assertIsNone(response.json()["campaign_id"])

    def test_inactive_staging_falls_back_to_the_default(self):
        old = EveLocation.objects.create(
            location_id=456,
            location_name="Old Keepstar",
            solar_system_id=345,
            solar_system_name="Elsewhere",
            short_name="Elsewhere",
            staging_active=False,
            fleets_active=False,
        )
        source = self.fleet(location=old)

        response = self.copy(source, self.fc)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["not_copied"], [NOT_COPIED_LOCATION])
        copy = EveFleet.objects.get(id=response.json()["id"])
        self.assertEqual(copy.location, self.staging)

    def test_removed_audience_is_a_clear_400(self):
        source = self.fleet(audience=None)

        response = self.copy(source, self.fc)

        self.assertEqual(response.status_code, 400)
        self.assertIn("audience no longer exists", response.json()["detail"])

    @patch("fleets.endpoints.helpers.queue_channel_message")
    def test_off_schedule_audience_is_announced_like_a_new_fleet(self, queue):
        hidden = EveFleetAudience.objects.get(name="Hidden")
        hidden.discord_channel_id = 4242
        hidden.save()
        source = self.fleet(audience=hidden)

        response = self.copy(source, self.fc)

        self.assertEqual(response.status_code, 200, response.content)
        queue.assert_called_once()
        self.assertEqual(queue.call_args.args[0], 4242)

    @patch("fleets.endpoints.helpers.queue_channel_message")
    def test_scheduled_audience_is_not_pinged(self, queue):
        source = self.fleet()

        self.copy(source, self.fc)

        queue.assert_not_called()


class GroupFleetCopyTests(FleetCopyTestBase):
    def setUp(self):
        super().setUp()
        self.group = make_tribe_group(allow_open_fleets=True)
        self.group.fleet_policy = TribeGroup.POLICY_MEMBERS
        self.group.save()
        self.group_fc = make_user("group_fc", perms=VIEW)
        add_member(self.group, self.group_fc)

    def group_fleet(self, **fields):
        values = {
            "created_by": self.group_fc,
            "audience": None,
            "host_group": self.group,
            "open_to_alliance": True,
            "on_schedule": True,
            "type": "training",
        }
        values.update(fields)
        return self.fleet(**values)

    @patch("fleets.endpoints.helpers.queue_channel_message")
    def test_group_fleet_copy_keeps_its_host_and_flags(self, queue):
        source = self.group_fleet()

        response = self.copy(source, self.group_fc)

        self.assertEqual(response.status_code, 200, response.content)
        copy = EveFleet.objects.get(id=response.json()["id"])
        self.assertEqual(copy.host_group, self.group)
        self.assertIsNone(copy.audience)
        self.assertTrue(copy.open_to_alliance)
        self.assertTrue(copy.on_schedule)
        self.assertEqual(copy.type, "training")
        self.assertEqual(response.json()["host_group"]["id"], self.group.id)
        queue.assert_not_called()

    def test_group_that_no_longer_opens_fleets_gets_a_members_only_copy(self):
        source = self.group_fleet()
        self.group.allow_open_fleets = False
        self.group.save()

        response = self.copy(source, self.group_fc)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["not_copied"], [NOT_COPIED_OPEN_TO_ALLIANCE]
        )
        copy = EveFleet.objects.get(id=response.json()["id"])
        self.assertFalse(copy.open_to_alliance)
        self.assertFalse(copy.on_schedule)

    def test_member_who_can_no_longer_publish_cannot_copy(self):
        source = self.group_fleet()
        self.group.fleet_policy = TribeGroup.POLICY_CHIEFS
        self.group.save()

        response = self.copy(source, self.group_fc)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(EveFleet.objects.count(), 1)


class FleetCanCopyTests(FleetCopyTestBase):
    def can_copy(self, fleet, user):
        response = self.call("get", f"/{fleet.id}", user)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["can_copy"]

    def test_fc_can_copy_their_fleet(self):
        self.assertTrue(self.can_copy(self.fleet(), self.fc))

    def test_pilot_cannot(self):
        self.assertFalse(self.can_copy(self.fleet(), self.pilot))

    def test_fc_without_fleets_create_cannot(self):
        former_fc = make_user("former_fc", perms=VIEW)
        self.assertFalse(
            self.can_copy(self.fleet(created_by=former_fc), former_fc)
        )

    def test_campaign_standing_fleet_cannot_be_copied(self):
        self.assertFalse(self.can_copy(self.fleet(type="standing"), self.fc))


class SaveCopiedFitsTests(FleetCopyTestBase):
    def setUp(self):
        super().setUp()
        self.copy_fleet = self.fleet(
            status="pending", start_time=self.next_week, doctrine=None
        )
        hull = EveFitting.objects.create(
            name="Hurricane [FL33T]",
            ship_id=24702,
            description="",
            eft_format=REFIT_EFT,
        )
        self.catalog_fit = EveFleetFitting.objects.create(
            eve_fleet=self.copy_fleet,
            fitting=hull,
            name=hull.name,
            ship_id=hull.ship_id,
        )
        self.manual_fit = EveFleetFitting.objects.create(
            eve_fleet=self.copy_fleet,
            name="Sabre tackle",
            ship_id=22456,
            eft_format=MANUAL_EFT,
            order=1,
        )
        self.refit = EveFleetFittingRefit.objects.create(
            eve_fleet=self.copy_fleet,
            fitting=hull,
            name="Armor",
            eft_format=REFIT_EFT,
        )

    def test_only_custom_fits_and_refits_with_an_eft_are_saved(self):
        EveFleetFittingRefit.objects.create(
            eve_fleet=self.copy_fleet,
            fitting=self.catalog_fit.fitting,
            name="Cargo only",
            cargo_modules="Nanite Repair Paste x100",
        )
        self.assertEqual(
            set(fits_to_save(self.copy_fleet)), {self.manual_fit, self.refit}
        )

    @patch("fleets.helpers.esi_fittings.publish_fitting")
    @patch("fleets.helpers.esi_fittings.fitting_publisher")
    def test_saves_under_the_copys_fc_once(self, publisher, publish):
        publisher.return_value = self.fc.eveplayer.primary_character
        publish.side_effect = [(9001, None), (9002, None)]

        self.assertEqual(save_copied_fits(self.copy_fleet), 2)

        publisher.assert_called_once_with(self.fc)
        self.manual_fit.refresh_from_db()
        self.refit.refresh_from_db()
        self.assertEqual(self.manual_fit.esi_fitting_id, 9001)
        self.assertEqual(self.refit.esi_fitting_id, 9002)
        labels = [call.args[2] for call in publish.call_args_list]
        self.assertEqual(
            labels, ["Sabre tackle", f"{self.refit.fitting.name} → Armor"]
        )
        # A second run has nothing left to save.
        self.assertEqual(save_copied_fits(self.copy_fleet), 0)
        self.assertEqual(publish.call_count, 2)

    @patch("fleets.helpers.esi_fittings.publish_fitting")
    @patch("fleets.helpers.esi_fittings.fitting_publisher", return_value=None)
    def test_no_fittings_scope_saves_nothing(self, publisher, publish):
        self.assertEqual(save_copied_fits(self.copy_fleet), 0)
        publisher.assert_called_once_with(self.fc)
        publish.assert_not_called()

    @patch("fleets.helpers.esi_fittings.publish_fitting")
    def test_cancelled_copy_saves_nothing(self, publish):
        self.copy_fleet.status = "cancelled"
        self.copy_fleet.save()

        self.assertEqual(save_copied_fits(self.copy_fleet), 0)
        publish.assert_not_called()

    @patch("fleets.tasks.on_commit_enqueue")
    def test_queued_only_when_there_is_a_fit_to_save(self, enqueue):
        queue_save_copied_fleet_fits(self.copy_fleet)
        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.args[1], (self.copy_fleet.id,))

        enqueue.reset_mock()
        empty = self.fleet(status="pending", start_time=self.next_week)
        queue_save_copied_fleet_fits(empty)
        enqueue.assert_not_called()
