"""Tests for doctrine/fitting approval workflow."""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse

from app.test import TestCase

from eveonline.models import EveLocation
from fittings.admin import _SELF_APPROVAL_WARNING
from fittings.helpers.change_request_display import (
    format_doctrine_change_request_html,
    format_doctrine_history_html,
    format_fitting_change_request_html,
    format_fitting_history_html,
)

from fittings.helpers.doctrine_changes import (
    approve_doctrine_change_request,
    cancel_doctrine_change_request,
    reject_doctrine_change_request,
    submit_doctrine_change_request,
)
from fittings.helpers.fitting_changes import (
    approve_fitting_change_request,
    cancel_fitting_change_request,
    reject_fitting_change_request,
    submit_fitting_change_request,
)
from fittings.helpers.permissions import (
    can_approve_doctrine_request,
    can_approve_fitting_request,
    effective_protection_tier,
    protection_tier_for_doctrine,
    users_who_can_approve_fitting_request,
)
from fittings.models import (
    ChangeRequestStatus,
    DOCTRINE_TYPE_EXPERIMENTAL,
    DOCTRINE_TYPE_NON_STRATEGIC,
    DOCTRINE_TYPE_STRATEGIC,
    EveDoctrine,
    EveDoctrineFitting,
    EveDoctrineHistory,
    EveFitting,
    EveFittingHistory,
)


def _perm(codename: str) -> Permission:
    ct = ContentType.objects.get(app_label="fittings", model="evedoctrine")
    return Permission.objects.get(content_type=ct, codename=codename)


class ProtectionTierTestCase(TestCase):
    def test_experimental_doctrine_has_no_tier(self):
        doctrine = EveDoctrine.objects.create(
            name="Exp",
            type=DOCTRINE_TYPE_EXPERIMENTAL,
            description="",
        )
        self.assertIsNone(protection_tier_for_doctrine(doctrine))

    def test_fitting_only_on_experimental(self):
        doctrine = EveDoctrine.objects.create(
            name="Exp",
            type=DOCTRINE_TYPE_EXPERIMENTAL,
            description="",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        self.assertIsNone(effective_protection_tier(fitting))

    def test_fitting_experimental_and_strategic(self):
        exp = EveDoctrine.objects.create(
            name="Exp",
            type=DOCTRINE_TYPE_EXPERIMENTAL,
            description="",
        )
        strat = EveDoctrine.objects.create(
            name="Strat",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="",
        )
        EveDoctrineFitting.objects.create(
            doctrine=exp, fitting=fitting, role="primary"
        )
        EveDoctrineFitting.objects.create(
            doctrine=strat, fitting=fitting, role="primary"
        )
        self.assertEqual("strategic", effective_protection_tier(fitting))

    def test_fitting_no_doctrine_links_has_no_tier(self):
        fitting = EveFitting.objects.create(
            name="Standalone",
            eft_format="[Rifter, Standalone]",
            ship_id=587,
            description="",
        )
        self.assertIsNone(effective_protection_tier(fitting))

    def test_fitting_only_on_non_strategic_doctrine(self):
        doctrine = EveDoctrine.objects.create(
            name="Skirmish",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        self.assertEqual("non_strategic", effective_protection_tier(fitting))


class PermissionMatrixTestCase(TestCase):
    """Skirmish vs strategic FC permission boundaries (S-5, ST-1)."""

    def _create_user(self, username):
        return User.objects.create(username=username)

    def test_skirmish_fc_approves_non_strategic_not_strategic(self):
        skirmish = self._create_user("skirmish")
        skirmish.user_permissions.add(
            _perm("approve_doctrine_non_strategic"),
            _perm("approve_doctrine_fitting_non_strategic"),
        )
        self.assertTrue(
            can_approve_doctrine_request(skirmish, "non_strategic")
        )
        self.assertTrue(can_approve_fitting_request(skirmish, "non_strategic"))
        self.assertFalse(can_approve_doctrine_request(skirmish, "strategic"))
        self.assertFalse(can_approve_fitting_request(skirmish, "strategic"))

    def test_strategic_fc_superset_for_non_strategic(self):
        strategic = self._create_user("strategic")
        strategic.user_permissions.add(_perm("approve_doctrine_strategic"))
        self.assertTrue(
            can_approve_doctrine_request(strategic, "non_strategic")
        )
        self.assertTrue(can_approve_doctrine_request(strategic, "strategic"))


class DoctrineChangeRequestTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.proposer = self.user
        self.proposer.user_permissions.add(
            _perm("change_doctrine_strategic"),
        )
        self.approver = self._create_user("approver")
        self.approver.user_permissions.add(
            _perm("approve_doctrine_strategic"),
        )

    def _create_user(self, username):
        return User.objects.create(username=username)

    def test_propose_strategic_doctrine_does_not_change_live(self):
        doctrine = EveDoctrine.objects.create(
            name="Old Name",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="old",
            latest_version="v1",
        )
        payload = {
            "name": "New Name",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "new",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        req = submit_doctrine_change_request(doctrine, payload, self.proposer)
        doctrine.refresh_from_db()
        self.assertEqual("Old Name", doctrine.name)
        self.assertIsNotNone(req)
        self.assertEqual(ChangeRequestStatus.PENDING, req.status)

    def test_approve_writes_history_and_live(self):
        doctrine = EveDoctrine.objects.create(
            name="Old",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="old",
            latest_version="version-1",
        )
        payload = {
            "name": "New",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "new",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        req = submit_doctrine_change_request(doctrine, payload, self.proposer)
        approve_doctrine_change_request(req, self.approver)
        doctrine.refresh_from_db()
        self.assertEqual("New", doctrine.name)
        self.assertEqual(
            1, EveDoctrineHistory.objects.filter(doctrine=doctrine).count()
        )

    def test_experimental_publishes_immediately(self):
        doctrine = EveDoctrine.objects.create(
            name="Exp",
            type=DOCTRINE_TYPE_EXPERIMENTAL,
            description="",
        )
        payload = {
            "name": "Exp Updated",
            "type": DOCTRINE_TYPE_EXPERIMENTAL,
            "description": "x",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        result = submit_doctrine_change_request(
            doctrine, payload, self.proposer
        )
        self.assertIsNone(result)
        doctrine.refresh_from_db()
        self.assertEqual("Exp Updated", doctrine.name)

    def test_reject_keeps_live_doctrine(self):
        doctrine = EveDoctrine.objects.create(
            name="Live",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="live",
            latest_version="v1",
        )
        payload = {
            "name": "Rejected",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "rejected",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        req = submit_doctrine_change_request(doctrine, payload, self.proposer)
        reject_doctrine_change_request(req, self.approver, review_note="no")
        doctrine.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual("Live", doctrine.name)
        self.assertEqual(ChangeRequestStatus.REJECTED, req.status)

    def test_cancel_by_submitter(self):
        doctrine = EveDoctrine.objects.create(
            name="Live",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
            latest_version="v1",
        )
        payload = {
            "name": "Cancelled",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "x",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        req = submit_doctrine_change_request(doctrine, payload, self.proposer)
        cancel_doctrine_change_request(req, self.proposer)
        req.refresh_from_db()
        self.assertEqual(ChangeRequestStatus.CANCELLED, req.status)
        doctrine.refresh_from_db()
        self.assertEqual("Live", doctrine.name)

    def test_duplicate_pending_blocked(self):
        doctrine = EveDoctrine.objects.create(
            name="D",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        payload = {
            "name": "A",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        submit_doctrine_change_request(doctrine, payload, self.proposer)
        with self.assertRaises(ValueError):
            submit_doctrine_change_request(doctrine, payload, self.proposer)

    def test_double_approve_raises(self):
        doctrine = EveDoctrine.objects.create(
            name="D",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
            latest_version="v1",
        )
        payload = {
            "name": "New",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "new",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        req = submit_doctrine_change_request(doctrine, payload, self.proposer)
        approve_doctrine_change_request(req, self.approver)
        with self.assertRaises(ValueError):
            approve_doctrine_change_request(req, self.approver)

    def test_approve_rejects_payload_tier_mismatch(self):
        doctrine = EveDoctrine.objects.create(
            name="D",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
            latest_version="v1",
        )
        payload = {
            "name": "New",
            "type": DOCTRINE_TYPE_EXPERIMENTAL,
            "description": "new",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        req = submit_doctrine_change_request(doctrine, payload, self.proposer)
        with self.assertRaises(ValueError):
            approve_doctrine_change_request(req, self.approver)

    def test_propose_without_permission_denied(self):
        doctrine = EveDoctrine.objects.create(
            name="D",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        outsider = self._create_user("outsider")
        payload = {
            "name": "X",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        with self.assertRaises(PermissionError):
            submit_doctrine_change_request(doctrine, payload, outsider)

    def test_non_strategic_doctrine_workflow(self):
        proposer = self.user
        proposer.user_permissions.add(_perm("change_doctrine_non_strategic"))
        approver = self._create_user("skirmish_fc")
        approver.user_permissions.add(_perm("approve_doctrine_non_strategic"))

        doctrine = EveDoctrine.objects.create(
            name="NS Old",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="old",
        )
        payload = {
            "name": "NS New",
            "type": DOCTRINE_TYPE_NON_STRATEGIC,
            "description": "new",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        req = submit_doctrine_change_request(doctrine, payload, proposer)
        approve_doctrine_change_request(req, approver)
        doctrine.refresh_from_db()
        self.assertEqual("NS New", doctrine.name)

    def test_pending_composition_not_exposed_on_api(self):
        """FM-2: doctrine composition in pending request is not on public API."""
        live_fitting = EveFitting.objects.create(
            name="Live Fit",
            eft_format="[Rifter, Live Fit]",
            ship_id=587,
            description="",
        )
        pending_fitting = EveFitting.objects.create(
            name="Pending Fit",
            eft_format="[Rifter, Pending Fit]",
            ship_id=587,
            description="",
        )
        doctrine = EveDoctrine.objects.create(
            name="Strat Doc",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=live_fitting, role="primary"
        )
        payload = {
            "name": "Strat Doc",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "",
            "composition": {
                "primary": [live_fitting.pk, pending_fitting.pk],
                "secondary": [],
                "support": [],
            },
            "location_ids": [],
        }
        submit_doctrine_change_request(doctrine, payload, self.proposer)

        response = self.client.get(f"/api/doctrines/{doctrine.id}")
        self.assertEqual(200, response.status_code)
        primary_ids = [f["id"] for f in response.json()["primary_fittings"]]
        self.assertEqual([live_fitting.pk], primary_ids)


class FittingChangeRequestTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.proposer = self.user
        self.proposer.user_permissions.add(
            _perm("change_doctrine_fitting_strategic"),
            _perm("change_doctrine_fitting_non_strategic"),
        )
        self.approver = self._create_user("fc")
        self.approver.user_permissions.add(
            _perm("approve_doctrine_fitting_strategic"),
            _perm("approve_doctrine_fitting_non_strategic"),
        )

    def _create_user(self, username):
        return User.objects.create(username=username)

    def test_propose_fitting_change_pending(self):
        doctrine = EveDoctrine.objects.create(
            name="Strat",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="d1",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        payload = {
            "eft_format": "[Rifter, Fit v2]",
            "description": "d2",
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "tags": [],
        }
        req = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload=payload,
            user=self.proposer,
        )
        fitting.refresh_from_db()
        self.assertEqual("d1", fitting.description)
        self.assertIsNotNone(req)

    def test_approve_fitting_writes_history(self):
        doctrine = EveDoctrine.objects.create(
            name="Strat",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="d1",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        version_before = fitting.latest_version
        payload = {
            "eft_format": "[Rifter, Fit v2]",
            "description": "d2",
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "tags": [],
        }
        req = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload=payload,
            user=self.proposer,
        )
        approve_fitting_change_request(req, self.approver)
        fitting.refresh_from_db()
        self.assertEqual("d2", fitting.description)
        self.assertEqual("Fit v2", fitting.name)
        self.assertNotEqual(version_before, fitting.latest_version)
        self.assertEqual(
            1, EveFittingHistory.objects.filter(fitting=fitting).count()
        )

    def test_approve_fitting_create_publishes(self):
        fitting = EveFitting.objects.create(
            name="New Fit",
            eft_format="[Rifter, New Fit]",
            ship_id=587,
            description="pending create",
        )
        fitting.delete()
        self.assertFalse(EveFitting.objects.filter(pk=fitting.pk).exists())
        payload = {
            "eft_format": "[Rifter, New Fit]",
            "description": "live description",
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "tags": [],
        }
        req = submit_fitting_change_request(
            fitting,
            change_kind="fitting_create",
            payload=payload,
            user=self.proposer,
        )
        approve_fitting_change_request(req, self.approver)
        live = EveFitting.objects.get(pk=fitting.pk)
        self.assertIsNone(live.deleted)
        self.assertEqual("live description", live.description)
        self.assertEqual("New Fit", live.name)

    def test_approve_fitting_delete_removes_live(self):
        fitting = EveFitting.objects.create(
            name="Doomed Fit",
            eft_format="[Rifter, Doomed Fit]",
            ship_id=587,
            description="bye",
        )
        payload = {
            "eft_format": fitting.eft_format,
            "description": fitting.description,
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "tags": [],
        }
        req = submit_fitting_change_request(
            fitting,
            change_kind="fitting_delete",
            payload=payload,
            user=self.proposer,
        )
        self.assertTrue(EveFitting.objects.filter(pk=fitting.pk).exists())
        approve_fitting_change_request(req, self.approver)
        self.assertFalse(EveFitting.objects.filter(pk=fitting.pk).exists())
        self.assertTrue(EveFitting.all_objects.filter(pk=fitting.pk).exists())

    def test_api_unaffected_by_pending(self):
        doctrine = EveDoctrine.objects.create(
            name="Strat",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="live",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="live",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload={
                "eft_format": "[Rifter, Pending]",
                "description": "pending",
                "aliases": "",
                "minimum_pod": "",
                "recommended_pod": "",
                "tags": [],
            },
            user=self.proposer,
        )
        response = self.client.get(f"/api/fittings/{fitting.id}")
        self.assertEqual(200, response.status_code)
        self.assertEqual("live", response.json()["description"])

        response = self.client.get(f"/api/doctrines/{doctrine.id}")
        self.assertEqual(200, response.status_code)
        self.assertEqual("live", response.json()["description"])

    def test_unlinked_fitting_requires_change_request(self):
        """Fittings with no doctrine link still queue changes for approval."""
        self.proposer.user_permissions.add(
            _perm("change_doctrine_fitting_non_strategic"),
        )
        fitting = EveFitting.objects.create(
            name="Standalone",
            eft_format="[Rifter, Standalone]",
            ship_id=587,
            description="before",
        )
        payload = {
            "eft_format": "[Rifter, Standalone]",
            "description": "after",
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "tags": [],
        }
        req = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload=payload,
            user=self.proposer,
        )
        self.assertIsNotNone(req)
        self.assertEqual("non_strategic", req.tier)
        fitting.refresh_from_db()
        self.assertEqual("before", fitting.description)

    def test_reject_keeps_live_fitting(self):
        doctrine = EveDoctrine.objects.create(
            name="Strat",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="live",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        req = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload={
                "eft_format": "[Rifter, Fit]",
                "description": "rejected",
                "aliases": "",
                "minimum_pod": "",
                "recommended_pod": "",
                "tags": [],
            },
            user=self.proposer,
        )
        reject_fitting_change_request(req, self.approver)
        fitting.refresh_from_db()
        self.assertEqual("live", fitting.description)

    def test_cancel_fitting_request_by_submitter(self):
        doctrine = EveDoctrine.objects.create(
            name="Strat",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="live",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        req = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload={
                "eft_format": "[Rifter, Fit]",
                "description": "pending",
                "aliases": "",
                "minimum_pod": "",
                "recommended_pod": "",
                "tags": [],
            },
            user=self.proposer,
        )
        cancel_fitting_change_request(req, self.proposer)
        fitting.refresh_from_db()
        self.assertEqual("live", fitting.description)

    def test_duplicate_pending_fitting_blocked(self):
        doctrine = EveDoctrine.objects.create(
            name="Strat",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        payload = {
            "eft_format": "[Rifter, Fit]",
            "description": "a",
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "tags": [],
        }
        submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload=payload,
            user=self.proposer,
        )
        with self.assertRaises(ValueError):
            submit_fitting_change_request(
                fitting,
                change_kind="fitting_versioned",
                payload=payload,
                user=self.proposer,
            )

    def test_approver_must_queue_change_request(self):
        """Users with approve permission still queue changes instead of publishing."""
        doctrine = EveDoctrine.objects.create(
            name="Strat",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
        )
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="before",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="primary"
        )
        self.approver.user_permissions.add(
            _perm("change_doctrine_fitting_strategic"),
        )
        payload = {
            "eft_format": "[Rifter, Fit]",
            "description": "published",
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "tags": [],
        }
        result = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload=payload,
            user=self.approver,
        )
        self.assertIsNotNone(result)
        fitting.refresh_from_db()
        self.assertEqual("before", fitting.description)


class ApproverRecipientTestCase(TestCase):
    """Who receives change-request review eligibility."""

    def _create_user(self, username, *, is_staff=False):
        return User.objects.create(username=username, is_staff=is_staff)

    def test_users_who_can_approve_fitting_non_strategic(self):
        skirmish = self._create_user("skirmish", is_staff=True)
        skirmish.user_permissions.add(
            _perm("approve_doctrine_fitting_non_strategic")
        )
        recipients = users_who_can_approve_fitting_request("non_strategic")
        self.assertIn(skirmish, recipients)

    def test_notify_recipients_exclude_non_staff(self):
        staff_approver = self._create_user("staff_approver")
        staff_approver.is_staff = True
        staff_approver.save(update_fields=["is_staff"])
        staff_approver.user_permissions.add(
            _perm("approve_doctrine_fitting_strategic")
        )
        non_staff = self._create_user("non_staff_approver")
        non_staff.user_permissions.add(
            _perm("approve_doctrine_fitting_strategic")
        )
        recipients = users_who_can_approve_fitting_request("strategic")
        self.assertIn(staff_approver, recipients)
        self.assertNotIn(non_staff, recipients)


class ChangeRequestDisplayTestCase(TestCase):
    def test_doctrine_change_request_display_shows_readable_diff(self):
        self.user.user_permissions.add(_perm("change_doctrine_strategic"))
        doctrine = EveDoctrine.objects.create(
            name="Old Doctrine",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="Old description",
            latest_version="v1",
        )
        fitting = EveFitting.objects.create(
            name="Hurricane Fleet",
            ship_id=123,
            eft_format="[Hurricane, Hurricane Fleet]\n",
            description="",
        )
        location = EveLocation.objects.create(
            location_id=60000001,
            location_name="Old Staging",
            short_name="OLD",
            solar_system_id=30000001,
            solar_system_name="Old System",
        )
        doctrine.locations.add(location)
        EveDoctrineFitting.objects.create(
            doctrine=doctrine,
            fitting=fitting,
            role="primary",
        )
        payload = {
            "name": "New Doctrine",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "New description",
            "composition": {
                "primary": [fitting.pk],
                "secondary": [],
                "support": [],
            },
            "location_ids": [],
        }
        change_request = submit_doctrine_change_request(
            doctrine, payload, self.user
        )
        html = str(format_doctrine_change_request_html(change_request))

        self.assertIn("New Doctrine", html)
        self.assertIn("Old Doctrine", html)
        self.assertIn("Hurricane Fleet", html)
        self.assertIn("OLD", html)
        self.assertNotIn('"composition"', html)

    def test_fitting_change_request_display_shows_eft_line_diff(self):
        self.user.user_permissions.add(
            _perm("change_doctrine_fitting_non_strategic"),
        )
        fitting = EveFitting.objects.create(
            name="Rifter SK",
            ship_id=587,
            eft_format="[Rifter, Rifter SK]\nHigh Slot A\nMid Slot B\n",
            description="",
        )
        payload = {
            "eft_format": "[Rifter, Rifter SK]\nHigh Slot A\nMid Slot C\n",
            "description": "",
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "tags": [],
        }
        change_request = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload=payload,
            user=self.user,
        )
        html = str(format_fitting_change_request_html(change_request))

        self.assertIn("Mid Slot B", html)
        self.assertIn("Mid Slot C", html)
        self.assertIn("− Mid Slot B", html)
        self.assertIn("+ Mid Slot C", html)
        self.assertNotIn('"eft_format"', html)


class ChangeRequestAdminActionsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.approver = User.objects.create(username="approver", is_staff=True)
        self.approver.user_permissions.add(_perm("approve_doctrine_strategic"))
        self.proposer = self.user
        self.proposer.user_permissions.add(_perm("change_doctrine_strategic"))

    def test_doctrine_change_request_detail_has_approve_action(self):
        doctrine = EveDoctrine.objects.create(
            name="Pending Doctrine",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
            latest_version="v1",
        )
        payload = {
            "name": "Updated Doctrine",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "updated",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        change_request = submit_doctrine_change_request(
            doctrine, payload, self.proposer
        )
        client = Client()
        client.force_login(self.approver)
        change_url = reverse(
            "admin:fittings_evedoctrinechangerequest_change",
            args=[change_request.pk],
        )
        response = client.get(change_url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Review action")
        self.assertContains(response, "Approve")

        response = client.post(
            change_url,
            {"review_action": "approve", "_save": "Save"},
        )
        self.assertEqual(302, response.status_code)
        change_request.refresh_from_db()
        doctrine.refresh_from_db()
        self.assertEqual(ChangeRequestStatus.APPROVED, change_request.status)
        self.assertEqual("Updated Doctrine", doctrine.name)

    def test_submitter_can_self_approve_with_warning(self):
        doctrine = EveDoctrine.objects.create(
            name="Self Approve Doctrine",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="",
            latest_version="v1",
        )
        payload = {
            "name": "Self Approved",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "self",
            "composition": {"primary": [], "secondary": [], "support": []},
            "location_ids": [],
        }
        change_request = submit_doctrine_change_request(
            doctrine, payload, self.proposer
        )
        self.proposer.is_staff = True
        self.proposer.save(update_fields=["is_staff"])
        client = Client()
        client.force_login(self.proposer)
        change_url = reverse(
            "admin:fittings_evedoctrinechangerequest_change",
            args=[change_request.pk],
        )
        response = client.get(change_url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "bypasses independent review")

        response = client.post(
            change_url,
            {"review_action": "approve", "_save": "Save"},
            follow=True,
        )
        self.assertEqual(200, response.status_code)
        self.assertContains(response, _SELF_APPROVAL_WARNING, count=1)
        change_request.refresh_from_db()
        doctrine.refresh_from_db()
        self.assertEqual(ChangeRequestStatus.APPROVED, change_request.status)
        self.assertEqual("Self Approved", doctrine.name)


class HistoryDisplayTestCase(TestCase):
    def test_doctrine_history_display_shows_readable_snapshot(self):
        doctrine = EveDoctrine.objects.create(
            name="History Doctrine",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="Snapshot description",
        )
        fitting = EveFitting.objects.create(
            name="Barghest Fleet",
            ship_id=33820,
            eft_format="[Barghest, Barghest Fleet]\n",
            description="",
        )
        history = EveDoctrineHistory.objects.create(
            doctrine=doctrine,
            superseded_version_id="version-abc",
            name="History Doctrine",
            type=DOCTRINE_TYPE_STRATEGIC,
            description="Snapshot description",
            composition={
                "primary": [fitting.pk],
                "secondary": [],
                "support": [],
            },
            location_ids=[],
        )
        html = str(format_doctrine_history_html(history))
        self.assertIn("Barghest Fleet", html)
        self.assertIn("Snapshot description", html)
        self.assertNotIn('"primary"', html)

    def test_fitting_history_display_shows_readable_snapshot(self):
        fitting = EveFitting.objects.create(
            name="Rifter SK",
            ship_id=587,
            eft_format="[Rifter, Rifter SK]\nHigh Slot\n",
            description="old desc",
            tags=["solo"],
        )
        history = EveFittingHistory.objects.create(
            fitting=fitting,
            superseded_version_id="fit-version",
            name="Rifter SK",
            ship_id=587,
            eft_format="[Rifter, Rifter SK]\nHigh Slot\n",
            description="old desc",
            tags=["solo"],
        )
        html = str(format_fitting_history_html(history))
        self.assertIn("Rifter", html)
        self.assertIn("old desc", html)
        self.assertIn("solo", html)
