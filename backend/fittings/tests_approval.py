"""Tests for doctrine/fitting approval workflow."""

from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType

from app.test import TestCase

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
    can_publish_fitting_change,
    effective_protection_tier,
    protection_tier_for_doctrine,
    users_who_can_approve_fitting_request,
)
from fittings.tasks import notify_fitting_change_request_proposed
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
        )
        self.approver = self._create_user("fc")
        self.approver.user_permissions.add(
            _perm("approve_doctrine_fitting_strategic"),
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
        self.assertNotEqual(version_before, fitting.latest_version)
        self.assertEqual(
            1, EveFittingHistory.objects.filter(fitting=fitting).count()
        )

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

    def test_unlinked_fitting_publishes_immediately(self):
        """R-F1/R-F2: fitting with no doctrine association updates live without a request."""
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
        result = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload=payload,
            user=self.proposer,
        )
        self.assertIsNone(result)
        fitting.refresh_from_db()
        self.assertEqual("after", fitting.description)

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

    def test_approver_can_publish_without_queue(self):
        """X-1 / ST-5: user with approve perm applies fitting change immediately."""
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
        self.assertTrue(can_publish_fitting_change(self.approver, "strategic"))
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
        self.assertIsNone(result)
        fitting.refresh_from_db()
        self.assertEqual("published", fitting.description)


class NotificationTasksTestCase(TestCase):
    """Discord notify on propose (mocked)."""

    def _create_user(self, username, *, is_staff=False):
        return User.objects.create(username=username, is_staff=is_staff)

    def test_notify_task_sends_dm_to_approvers(self):
        proposer = self._create_user("proposer")
        proposer.user_permissions.add(
            _perm("change_doctrine_fitting_strategic")
        )
        approver = self._create_user("approver", is_staff=True)
        approver.user_permissions.add(
            _perm("approve_doctrine_fitting_strategic")
        )
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
        req = submit_fitting_change_request(
            fitting,
            change_kind="fitting_versioned",
            payload={
                "eft_format": "[Rifter, X]",
                "description": "x",
                "aliases": "",
                "minimum_pod": "",
                "recommended_pod": "",
                "tags": [],
            },
            user=proposer,
        )
        self.assertIsNotNone(req)
        with patch("fittings.helpers.notifications._send_dm") as mock_dm:
            notify_fitting_change_request_proposed(req.pk)
            self.assertGreaterEqual(mock_dm.call_count, 1)
            dm_users = [call.args[0] for call in mock_dm.call_args_list]
            self.assertIn(approver, dm_users)

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
