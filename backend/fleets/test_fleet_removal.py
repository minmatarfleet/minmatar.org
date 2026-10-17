"""Removing a fleet keeps attendance and SRP history."""

from unittest.mock import MagicMock, patch

import jwt
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.db.models import ProtectedError
from django.test import Client

from app.test import TestCase
from fleets.helpers.removal import CANCELLED, DELETED, remove_fleet
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from srp.models import EveFleetShipReimbursement


class FleetRemovalTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.fleet = make_test_fleet("Removal test", self.user)

    def _ran(self, fleet):
        instance = EveFleetInstance.objects.create(
            id=4242 + fleet.id, eve_fleet=fleet
        )
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=2001,
            character_name="Pilot",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=587,
            ship_name="Rifter",
            solar_system_id=30002097,
            solar_system_name="Dal",
            squad_id=1,
            wing_id=1,
        )
        return instance

    def _claim(self, fleet):
        return EveFleetShipReimbursement.objects.create(
            fleet=fleet,
            external_killmail_link="https://zkillboard.com/kill/1/",
            killmail_id=1,
            character_id=2001,
            character_name="Pilot",
            primary_character_id=2001,
            primary_character_name="Pilot",
            amount=20_000_000,
            ship_name="Rifter",
            ship_type_id=587,
            user=self.user,
            status="approved",
        )

    def _delete(self, fleet):
        return self.client.delete(
            f"{BASE_URL}/{fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_a_fleet_that_never_ran_is_deleted(self):
        response = self._delete(self.fleet)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EveFleet.objects.filter(id=self.fleet.id).exists())

    def test_a_fleet_that_ran_is_cancelled_and_keeps_attendance(self):
        instance = self._ran(self.fleet)

        response = self._delete(self.fleet)

        self.assertEqual(response.status_code, 200)
        self.fleet.refresh_from_db()
        self.assertEqual(self.fleet.status, "cancelled")
        instance.refresh_from_db()
        self.assertIsNotNone(instance.end_time)
        self.assertEqual(
            EveFleetInstanceMember.objects.filter(
                eve_fleet_instance=instance
            ).count(),
            1,
        )

    def test_a_fleet_with_srp_claims_is_cancelled_and_keeps_them(self):
        claim = self._claim(self.fleet)

        response = self._delete(self.fleet)

        self.assertEqual(response.status_code, 200)
        self.fleet.refresh_from_db()
        self.assertEqual(self.fleet.status, "cancelled")
        claim.refresh_from_db()
        self.assertEqual(claim.fleet_id, self.fleet.id)
        self.assertEqual(claim.status, "approved")

    def test_no_code_path_can_cascade_srp_claims_away(self):
        self._claim(self.fleet)
        with self.assertRaises(ProtectedError):
            self.fleet.delete()
        self.assertEqual(
            EveFleetShipReimbursement.objects.filter(fleet=self.fleet).count(),
            1,
        )

    def test_remove_fleet_reports_what_it_did(self):
        other = make_test_fleet("Never ran", self.user)
        self._ran(self.fleet)
        self.assertEqual(remove_fleet(self.fleet), CANCELLED)
        self.assertEqual(remove_fleet(other), DELETED)

    def test_a_stranger_still_cannot_remove_a_fleet(self):
        stranger = User.objects.create(username="stranger")
        token = jwt.encode(
            {"user_id": stranger.id}, settings.SECRET_KEY, algorithm="HS256"
        )
        response = self.client.delete(
            f"{BASE_URL}/{self.fleet.id}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(EveFleet.objects.filter(id=self.fleet.id).exists())


class FleetAdminRemovalTestCase(TestCase):
    def setUp(self):
        super().setUp()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.admin = User.objects.create(
            username="fleet-admin", is_staff=True, is_superuser=True
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def _post_delete(self, fleet):
        return self.client.post(
            f"/admin/fleets/evefleet/{fleet.id}/delete/", {"post": "yes"}
        )

    def test_admin_refuses_to_delete_a_fleet_that_ran(self):
        # Attendance rows have no admin delete permission, so the admin
        # already refused; this pins that down.
        fleet = make_test_fleet("Ran", self.user)
        EveFleetInstance.objects.create(id=777, eve_fleet=fleet)

        response = self._post_delete(fleet)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(EveFleet.objects.filter(id=fleet.id).exists())

    def test_admin_refuses_to_delete_a_fleet_with_srp_claims(self):
        fleet = make_test_fleet("Claimed", self.user)
        EveFleetShipReimbursement.objects.create(
            fleet=fleet,
            external_killmail_link="https://zkillboard.com/kill/1/",
            killmail_id=1,
            character_id=2001,
            character_name="Pilot",
            primary_character_id=2001,
            primary_character_name="Pilot",
            amount=20_000_000,
            ship_name="Rifter",
            ship_type_id=587,
        )

        response = self._post_delete(fleet)

        self.assertContains(response, "protected related objects")
        self.assertTrue(EveFleet.objects.filter(id=fleet.id).exists())

    def test_admin_bulk_delete_refuses_too(self):
        fleet = make_test_fleet("Ran", self.user)
        EveFleetInstance.objects.create(id=778, eve_fleet=fleet)
        unused = make_test_fleet("Unused", self.user)

        self.client.post(
            "/admin/fleets/evefleet/",
            {
                "action": "delete_selected",
                "_selected_action": [fleet.id, unused.id],
                "post": "yes",
            },
        )

        self.assertTrue(EveFleet.objects.filter(id=fleet.id).exists())

    def test_admin_still_deletes_a_fleet_that_never_ran(self):
        fleet = make_test_fleet("Unused", self.user)
        self._post_delete(fleet)
        self.assertFalse(EveFleet.objects.filter(id=fleet.id).exists())


def bootstrap_local_unaligned_post(**kwargs):
    # Imported late: importing npsi_local before fleets.endpoints is a
    # pre-existing import cycle (npsi_actions -> endpoints -> npsi.auth).
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.npsi_local import (
        bootstrap_local_unaligned_post as bootstrap,
    )

    return bootstrap(**kwargs)


class NpsiForceRepostTestCase(TestCase):
    def setUp(self):
        super().setUp()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        self.user.user_permissions.add(
            Permission.objects.get(codename="add_evefleet")
        )

    @patch("fleets.helpers.npsi_ingest.DiscordClient", MagicMock())
    def test_force_repost_cancels_a_fleet_that_ran(self):
        _, old = bootstrap_local_unaligned_post(summary="Roam")
        EveFleetInstance.objects.create(id=9001, eve_fleet=old)

        _, new = bootstrap_local_unaligned_post(summary="Roam", force=True)

        self.assertNotEqual(new.id, old.id)
        old.refresh_from_db()
        self.assertEqual(old.status, "cancelled")
        self.assertTrue(EveFleetInstance.objects.filter(id=9001).exists())

    @patch("fleets.helpers.npsi_ingest.DiscordClient", MagicMock())
    def test_force_repost_still_deletes_a_fleet_that_never_ran(self):
        _, old = bootstrap_local_unaligned_post(summary="Roam")

        bootstrap_local_unaligned_post(summary="Roam", force=True)

        self.assertFalse(EveFleet.objects.filter(id=old.id).exists())
