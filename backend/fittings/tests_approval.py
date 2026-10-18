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
    apply_doctrine_payload,
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
    EveFittingRefit,
    composition_snapshot_for_doctrine,
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


class DoctrineUtilityRoleTestCase(TestCase):
    """Utility fits (cynos, boosters) are a fourth doctrine role."""

    def setUp(self):
        super().setUp()
        self.doctrine = EveDoctrine.objects.create(
            name="Utility Doc",
            type=DOCTRINE_TYPE_EXPERIMENTAL,
            description="",
        )
        self.primary = EveFitting.objects.create(
            name="Hurricane Fleet",
            eft_format="[Hurricane, Hurricane Fleet]",
            ship_id=24702,
            description="",
        )
        self.cyno = EveFitting.objects.create(
            name="Atron Cyno",
            eft_format="[Atron, Atron Cyno]",
            ship_id=608,
            description="",
        )

    def _payload(self, composition):
        return {
            "name": "Utility Doc",
            "type": DOCTRINE_TYPE_EXPERIMENTAL,
            "description": "",
            "composition": composition,
            "location_ids": [],
        }

    def test_apply_payload_links_utility_fits(self):
        apply_doctrine_payload(
            self.doctrine,
            self._payload(
                {"primary": [self.primary.pk], "utility": [self.cyno.pk]}
            ),
        )
        self.assertEqual(
            "utility",
            EveDoctrineFitting.objects.get(
                doctrine=self.doctrine, fitting=self.cyno
            ).role,
        )
        self.assertEqual(
            [self.cyno.pk],
            composition_snapshot_for_doctrine(self.doctrine)["utility"],
        )

        # A later payload without utility drops the link.
        apply_doctrine_payload(
            self.doctrine, self._payload({"primary": [self.primary.pk]})
        )
        self.assertFalse(
            EveDoctrineFitting.objects.filter(
                doctrine=self.doctrine, role="utility"
            ).exists()
        )

    def test_api_returns_utility_fittings(self):
        EveDoctrineFitting.objects.create(
            doctrine=self.doctrine, fitting=self.primary, role="primary"
        )
        EveDoctrineFitting.objects.create(
            doctrine=self.doctrine, fitting=self.cyno, role="utility"
        )
        for url in (f"/api/doctrines/{self.doctrine.id}", "/api/doctrines/"):
            body = self.client.get(url).json()
            doctrine = body[0] if isinstance(body, list) else body
            self.assertEqual(
                [self.cyno.pk], [f["id"] for f in doctrine["utility_fittings"]]
            )
            self.assertEqual(
                [self.primary.pk],
                [f["id"] for f in doctrine["primary_fittings"]],
            )

    def test_change_request_html_shows_utility(self):
        self.user.user_permissions.add(_perm("change_doctrine_strategic"))
        req = submit_doctrine_change_request(
            EveDoctrine.objects.create(
                name="Strat Utility",
                type=DOCTRINE_TYPE_STRATEGIC,
                description="",
            ),
            {
                "name": "Strat Utility",
                "type": DOCTRINE_TYPE_STRATEGIC,
                "description": "",
                "composition": {"utility": [self.cyno.pk]},
                "location_ids": [],
            },
            self.user,
        )
        html = format_doctrine_change_request_html(req)
        self.assertIn("Utility", html)
        self.assertIn("Atron Cyno", html)


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

    def test_approve_eft_change_marks_refits_needs_review(self):
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="d1",
        )
        refit = EveFittingRefit.objects.create(
            base_fitting=fitting,
            name="Scan",
            eft_format="[Rifter, Scan]",
            description="",
        )
        self.assertFalse(refit.needs_review)
        payload = {
            "eft_format": "[Rifter, Fit v2]",
            "description": "d1",
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
        refit.refresh_from_db()
        self.assertTrue(refit.needs_review)

    def test_approve_description_only_does_not_mark_refits(self):
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="d1",
        )
        refit = EveFittingRefit.objects.create(
            base_fitting=fitting,
            name="Scan",
            eft_format="[Rifter, Scan]",
            description="",
        )
        payload = {
            "eft_format": "[Rifter, Fit]",
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
        refit.refresh_from_db()
        self.assertFalse(refit.needs_review)

    def test_approve_refit_update_clears_needs_review(self):
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="d1",
        )
        refit = EveFittingRefit.objects.create(
            base_fitting=fitting,
            name="Scan",
            eft_format="[Rifter, Scan]",
            description="",
            needs_review=True,
        )
        payload = {
            "name": "Scan v2",
            "eft_format": "[Rifter, Scan v2]",
            "description": "updated",
        }
        req = submit_fitting_change_request(
            fitting,
            change_kind="refit_update",
            payload=payload,
            user=self.proposer,
            refit=refit,
        )
        approve_fitting_change_request(req, self.approver)
        refit.refresh_from_db()
        self.assertEqual("Scan v2", refit.name)
        self.assertFalse(refit.needs_review)

    def test_approve_refit_delete_clears_refit_and_keeps_request(self):
        fitting = EveFitting.objects.create(
            name="Fit",
            eft_format="[Rifter, Fit]",
            ship_id=587,
            description="d1",
        )
        refit = EveFittingRefit.objects.create(
            base_fitting=fitting,
            name="Scan",
            eft_format="[Rifter, Scan]",
            description="",
        )
        payload = {
            "name": refit.name,
            "eft_format": refit.eft_format,
            "description": "",
        }
        req = submit_fitting_change_request(
            fitting,
            change_kind="refit_delete",
            payload=payload,
            user=self.proposer,
            refit=refit,
        )
        approve_fitting_change_request(req, self.approver)
        self.assertFalse(EveFittingRefit.objects.filter(pk=refit.pk).exists())
        req.refresh_from_db()
        self.assertEqual(ChangeRequestStatus.APPROVED, req.status)
        self.assertIsNone(req.refit_id)

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


class DoctrineAdminAddTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=["is_staff", "is_superuser"])
        self.client = Client()
        self.client.force_login(self.user)
        self.fitting = EveFitting.objects.create(
            name="[FL33T] Inquisitor",
            ship_id=12034,
            eft_format="[Inquisitor, Inquisitor]",
            description="",
        )
        self.location = EveLocation.objects.create(
            location_id=60008494,
            location_name="Amamake",
            short_name="Amamake",
            solar_system_id=30003067,
            solar_system_name="Amamake",
        )

    def _doctrine_post(self, **overrides):
        data = {
            "name": "Plexing",
            "type": DOCTRINE_TYPE_NON_STRATEGIC,
            "description": "Mixture of armor ships.",
            "primary_fittings": [self.fitting.pk],
            "secondary_fittings": [self.fitting.pk],
            "support_fittings": [],
            "utility_fittings": [],
            "locations": [self.location.pk],
            "_save": "Save",
        }
        data.update(overrides)
        return data

    def test_add_non_strategic_doctrine_queues_without_500(self):
        response = self.client.post(
            reverse("admin:fittings_evedoctrine_add"),
            self._doctrine_post(),
        )
        self.assertEqual(302, response.status_code, response.content[:500])
        doctrine = EveDoctrine.objects.get(name="Plexing")
        self.assertFalse(
            EveDoctrineFitting.objects.filter(doctrine=doctrine).exists()
        )
        self.assertFalse(doctrine.locations.exists())
        change_request = doctrine.change_requests.get()
        self.assertEqual(ChangeRequestStatus.PENDING, change_request.status)
        self.assertEqual(
            [self.fitting.pk],
            change_request.payload["composition"]["primary"],
        )
        self.assertEqual(
            [self.location.pk], change_request.payload["location_ids"]
        )

    def test_change_protected_doctrine_does_not_publish_locations(self):
        doctrine = EveDoctrine.objects.create(
            name="Plexing",
            type=DOCTRINE_TYPE_NON_STRATEGIC,
            description="old",
        )
        response = self.client.post(
            reverse("admin:fittings_evedoctrine_change", args=[doctrine.pk]),
            self._doctrine_post(description="updated"),
        )
        self.assertEqual(302, response.status_code, response.content[:500])
        doctrine.refresh_from_db()
        self.assertEqual("old", doctrine.description)
        self.assertFalse(doctrine.locations.exists())
        change_request = doctrine.change_requests.get()
        self.assertEqual(
            [self.location.pk], change_request.payload["location_ids"]
        )

    def test_add_experimental_doctrine_applies_immediately(self):
        response = self.client.post(
            reverse("admin:fittings_evedoctrine_add"),
            self._doctrine_post(type=DOCTRINE_TYPE_EXPERIMENTAL),
        )
        self.assertEqual(302, response.status_code, response.content[:500])
        doctrine = EveDoctrine.objects.get(name="Plexing")
        self.assertTrue(
            EveDoctrineFitting.objects.filter(
                doctrine=doctrine, fitting=self.fitting, role="primary"
            ).exists()
        )
        self.assertTrue(
            doctrine.locations.filter(pk=self.location.pk).exists()
        )
        self.assertFalse(doctrine.change_requests.exists())


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
        )
        fitting.set_tag_slugs(["nanogang"], write_history=False)
        history = EveFittingHistory.objects.create(
            fitting=fitting,
            superseded_version_id="fit-version",
            name="Rifter SK",
            ship_id=587,
            eft_format="[Rifter, Rifter SK]\nHigh Slot\n",
            description="old desc",
            tags=["nanogang"],
        )
        html = str(format_fitting_history_html(history))
        self.assertIn("Rifter", html)
        self.assertIn("old desc", html)
        self.assertIn("nanogang", html)
