"""API tests for the doctrine/fitting editor and review queue."""

from django.contrib.auth.models import User
from django.test import Client

from app.test import TestCase
from app.testing import make_token
from fittings.models import (
    DOCTRINE_TYPE_EXPERIMENTAL,
    DOCTRINE_TYPE_NON_STRATEGIC,
    DOCTRINE_TYPE_STRATEGIC,
    ChangeRequestStatus,
    EveDoctrine,
    EveDoctrineChangeRequest,
    EveDoctrineFitting,
    EveFitting,
    EveFittingChangeRequest,
    EveFittingHistory,
)
from groups.helpers.feature_access import clear_feature_cache
from users.helpers import add_user_permission

EFT = "[Rifter, Rifter Fit]\nDamage Control II"
NEW_EFT = "[Rifter, Rifter Fit]\nDamage Control II\nSmall Armor Repairer II"


class ChangeRequestApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.fitting = EveFitting.objects.create(
            name="Rifter Fit", eft_format=EFT, ship_id=587, description="old"
        )
        self.strategic = EveDoctrine.objects.create(
            name="Strat", type=DOCTRINE_TYPE_STRATEGIC, description="d"
        )
        EveDoctrineFitting.objects.create(
            doctrine=self.strategic, fitting=self.fitting, role="primary"
        )
        self.second = EveFitting.objects.create(
            name="Other Fit",
            eft_format="[Rifter, Other Fit]",
            ship_id=587,
            description="",
        )

    def _auth(self, user=None):
        return {
            "HTTP_AUTHORIZATION": f"Bearer {make_token(user or self.user)}"
        }

    def _grant(self, *codenames, user=None):
        for codename in codenames:
            add_user_permission(user or self.user, codename)
        clear_feature_cache()

    def _post(self, path, body, user=None):
        return self.client.post(
            f"/api/{path}",
            body,
            content_type="application/json",
            **self._auth(user),
        )

    def _fitting_body(self, **overrides):
        body = {
            "eft_format": NEW_EFT,
            "description": "new",
            "tags": [],
            "preview": False,
        }
        body.update(overrides)
        return body

    def _doctrine_body(self, **overrides):
        body = {
            "name": "Strat",
            "type": DOCTRINE_TYPE_STRATEGIC,
            "description": "d",
            "composition": {
                "primary": [self.fitting.id],
                "secondary": [self.second.id],
                "support": [],
                "utility": [],
            },
            "preview": False,
        }
        body.update(overrides)
        return body

    def test_endpoints_require_a_login(self):
        self.assertEqual(
            401, self.client.get("/api/change-requests/").status_code
        )
        response = self.client.post(
            f"/api/fittings/{self.fitting.id}/change-requests",
            self._fitting_body(),
            content_type="application/json",
        )
        self.assertEqual(401, response.status_code)

    def test_fitting_submit_forbidden_without_access(self):
        response = self._post(
            f"fittings/{self.fitting.id}/change-requests",
            self._fitting_body(),
        )
        self.assertEqual(403, response.status_code)
        self.assertEqual(0, EveFittingChangeRequest.objects.count())
        self.assertEqual(
            403,
            self.client.get(
                "/api/change-requests/", **self._auth()
            ).status_code,
        )

    def test_fitting_preview_returns_diff_and_saves_nothing(self):
        self._grant("change_doctrine_fitting_strategic")
        response = self._post(
            f"fittings/{self.fitting.id}/change-requests",
            self._fitting_body(preview=True),
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIsNone(body["request"])
        eft = [d for d in body["diffs"] if d["field"] == "eft_format"][0]
        self.assertIn(
            {"kind": "add", "text": "Small Armor Repairer II"}, eft["lines"]
        )
        self.assertEqual(0, EveFittingChangeRequest.objects.count())

    def test_fitting_submit_creates_pending_request(self):
        self._grant("change_doctrine_fitting_strategic")
        response = self._post(
            f"fittings/{self.fitting.id}/change-requests",
            self._fitting_body(),
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("pending", response.json()["request"]["status"])
        self.assertEqual("strategic", response.json()["request"]["tier"])
        self.fitting.refresh_from_db()
        self.assertEqual(EFT, self.fitting.eft_format)
        again = self._post(
            f"fittings/{self.fitting.id}/change-requests",
            self._fitting_body(),
        )
        self.assertEqual(409, again.status_code)

    def test_fitting_validation(self):
        self._grant("change_doctrine_fitting_strategic")
        path = f"fittings/{self.fitting.id}/change-requests"
        cases = {
            "no header": self._fitting_body(eft_format="Damage Control II"),
            "other hull": self._fitting_body(eft_format="[Tristan, X]\nA"),
            "bad tag": self._fitting_body(tags=["nonsense"]),
            "no change": self._fitting_body(eft_format=EFT, description="old"),
        }
        for name, body in cases.items():
            with self.subTest(name):
                self.assertEqual(400, self._post(path, body).status_code)
        missing = self._post(
            "fittings/99999/change-requests", self._fitting_body()
        )
        self.assertEqual(404, missing.status_code)

    def test_proposer_cannot_approve_but_approver_can_with_history(self):
        self._grant("change_doctrine_fitting_strategic")
        created = self._post(
            f"fittings/{self.fitting.id}/change-requests",
            self._fitting_body(),
        ).json()["request"]
        review = f"change-requests/fitting/{created['id']}/review"
        denied = self._post(review, {"action": "approve"})
        self.assertEqual(403, denied.status_code)

        approver = User.objects.create(username="approver")
        self._grant("approve_doctrine_fitting_strategic", user=approver)
        queue = self.client.get(
            "/api/change-requests/", **self._auth(approver)
        )
        self.assertEqual(1, len(queue.json()))
        self.assertTrue(queue.json()[0]["can_review"])
        approved = self._post(
            review, {"action": "approve", "review_note": "ok"}, user=approver
        )
        self.assertEqual(200, approved.status_code)
        self.assertEqual("approved", approved.json()["status"])
        self.fitting.refresh_from_db()
        self.assertEqual(NEW_EFT, self.fitting.eft_format)
        self.assertTrue(
            EveFittingHistory.objects.filter(fitting=self.fitting).exists()
        )
        replay = self._post(review, {"action": "approve"}, user=approver)
        self.assertEqual(409, replay.status_code)

    def test_reject_and_cancel(self):
        self._grant("change_doctrine_fitting_strategic")
        created = self._post(
            f"fittings/{self.fitting.id}/change-requests",
            self._fitting_body(),
        ).json()["request"]
        review = f"change-requests/fitting/{created['id']}/review"
        cancelled = self._post(review, {"action": "cancel"})
        self.assertEqual("cancelled", cancelled.json()["status"])

        second = self._post(
            f"fittings/{self.fitting.id}/change-requests",
            self._fitting_body(),
        ).json()["request"]
        approver = User.objects.create(username="approver")
        self._grant("approve_doctrine_fitting_strategic", user=approver)
        rejected = self._post(
            f"change-requests/fitting/{second['id']}/review",
            {"action": "reject", "review_note": "no"},
            user=approver,
        )
        self.assertEqual("rejected", rejected.json()["status"])
        self.fitting.refresh_from_db()
        self.assertEqual(EFT, self.fitting.eft_format)
        bad = self._post(review, {"action": "explode"})
        self.assertEqual(400, bad.status_code)

    def test_strangers_cannot_cancel_others_requests(self):
        self._grant("change_doctrine_fitting_strategic")
        created = self._post(
            f"fittings/{self.fitting.id}/change-requests",
            self._fitting_body(),
        ).json()["request"]
        other = User.objects.create(username="other")
        self._grant("change_doctrine_fitting_strategic", user=other)
        response = self._post(
            f"change-requests/fitting/{created['id']}/review",
            {"action": "cancel"},
            user=other,
        )
        self.assertEqual(403, response.status_code)

    def test_doctrine_submit_and_approve(self):
        self._grant("change_doctrine_strategic")
        preview = self._post(
            f"doctrines/{self.strategic.id}/change-requests",
            self._doctrine_body(preview=True),
        )
        self.assertEqual(200, preview.status_code)
        labels = {d["label"] for d in preview.json()["diffs"]}
        self.assertEqual({"Academy"}, labels)

        created = self._post(
            f"doctrines/{self.strategic.id}/change-requests",
            self._doctrine_body(),
        ).json()["request"]
        approver = User.objects.create(username="approver")
        self._grant("approve_doctrine_strategic", user=approver)
        approved = self._post(
            f"change-requests/doctrine/{created['id']}/review",
            {"action": "approve"},
            user=approver,
        )
        self.assertEqual(200, approved.status_code)
        self.assertTrue(
            EveDoctrineFitting.objects.filter(
                doctrine=self.strategic, fitting=self.second, role="secondary"
            ).exists()
        )
        self.assertEqual(
            1,
            self.strategic.version_history.count(),
        )

    def test_capitals_role_with_note_through_review(self):
        self._grant("change_doctrine_strategic")
        dread = EveFitting.objects.create(
            name="Anti-Cap Naglfar",
            eft_format="[Naglfar, Anti-Cap Naglfar]",
            ship_id=19722,
            description="",
        )
        body = self._doctrine_body(note="We bring two dreads now.")
        body["composition"]["capitals"] = [dread.id]
        preview = self._post(
            f"doctrines/{self.strategic.id}/change-requests",
            {**body, "preview": True},
        )
        self.assertEqual(200, preview.status_code)
        labels = {d["label"] for d in preview.json()["diffs"]}
        self.assertIn("Capitals", labels)

        created = self._post(
            f"doctrines/{self.strategic.id}/change-requests", body
        ).json()["request"]
        self.assertEqual("We bring two dreads now.", created["submit_note"])
        listed = self.client.get(
            "/api/change-requests/", **self._auth()
        ).json()
        self.assertEqual("We bring two dreads now.", listed[0]["submit_note"])

        approver = User.objects.create(username="approver")
        self._grant("approve_doctrine_strategic", user=approver)
        self._post(
            f"change-requests/doctrine/{created['id']}/review",
            {"action": "approve"},
            user=approver,
        )
        self.assertTrue(
            EveDoctrineFitting.objects.filter(
                doctrine=self.strategic, fitting=dread, role="capitals"
            ).exists()
        )
        doctrine = self.client.get(
            f"/api/doctrines/{self.strategic.id}"
        ).json()
        self.assertEqual(
            [dread.id], [f["id"] for f in doctrine["capitals_fittings"]]
        )

    def test_doctrine_validation(self):
        self._grant("change_doctrine_strategic")
        path = f"doctrines/{self.strategic.id}/change-requests"
        unknown_fit = self._doctrine_body()
        unknown_fit["composition"]["support"] = [99999]
        cases = {
            "unknown type": self._doctrine_body(type="weird"),
            "unknown fitting": unknown_fit,
            "no change": self._doctrine_body(
                composition={
                    "primary": [self.fitting.id],
                    "secondary": [],
                    "support": [],
                    "utility": [],
                }
            ),
        }
        for name, body in cases.items():
            with self.subTest(name):
                self.assertEqual(400, self._post(path, body).status_code)
        self.assertEqual(0, EveDoctrineChangeRequest.objects.count())

    def test_review_queue_lists_only_pending_by_default(self):
        self._grant("change_doctrine_fitting_strategic")
        created = self._post(
            f"fittings/{self.fitting.id}/change-requests",
            self._fitting_body(),
        ).json()["request"]
        EveFittingChangeRequest.objects.filter(pk=created["id"]).update(
            status=ChangeRequestStatus.APPROVED
        )
        queue = self.client.get("/api/change-requests/", **self._auth())
        self.assertEqual([], queue.json())
        history = self.client.get(
            "/api/change-requests/?status=all", **self._auth()
        )
        self.assertEqual(1, len(history.json()))

    def test_change_category_across_tiers(self):
        self._grant("change_doctrine_strategic")
        response = self._post(
            f"doctrines/{self.strategic.id}/change-requests",
            self._doctrine_body(type=DOCTRINE_TYPE_EXPERIMENTAL),
        )
        self.assertEqual(200, response.status_code, response.content)
        request = response.json()["request"]
        self.assertEqual("strategic", request["tier"])
        type_diff = next(d for d in request["diffs"] if d["field"] == "type")
        self.assertIn(
            "Experimental", [line["text"] for line in type_diff["lines"]]
        )
        self.strategic.refresh_from_db()
        self.assertEqual(DOCTRINE_TYPE_STRATEGIC, self.strategic.type)

    def test_leaving_experimental_is_reviewed(self):
        self._grant("change_doctrine_non_strategic")
        experimental = EveDoctrine.objects.create(
            name="Exp", type=DOCTRINE_TYPE_EXPERIMENTAL, description="d"
        )
        response = self._post(
            f"doctrines/{experimental.id}/change-requests",
            self._doctrine_body(name="Exp", type=DOCTRINE_TYPE_NON_STRATEGIC),
        )
        self.assertEqual(200, response.status_code, response.content)
        # Leaving Experimental for a reviewed category is itself reviewed.
        self.assertEqual("non_strategic", response.json()["request"]["tier"])
        experimental.refresh_from_db()
        self.assertEqual(DOCTRINE_TYPE_EXPERIMENTAL, experimental.type)

    def test_retire_experimental_doctrine(self):
        self._grant("change_doctrine_strategic")
        experimental = EveDoctrine.objects.create(
            name="Exp", type=DOCTRINE_TYPE_EXPERIMENTAL, description="d"
        )
        path = f"doctrines/{experimental.id}/change-requests"
        body = self._doctrine_body(
            name="Exp", type=DOCTRINE_TYPE_EXPERIMENTAL, retired=True
        )
        body["composition"] = {"primary": [], "secondary": []}
        response = self._post(path, body)
        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(response.json()["applied"])
        experimental.refresh_from_db()
        self.assertTrue(experimental.retired)

        listed = self.client.get("/api/doctrines/").json()
        self.assertNotIn(experimental.id, [d["id"] for d in listed])
        everything = self.client.get(
            "/api/doctrines/?include_retired=true"
        ).json()
        row = next(d for d in everything if d["id"] == experimental.id)
        self.assertTrue(row["retired"])
        single = self.client.get(f"/api/doctrines/{experimental.id}").json()
        self.assertTrue(single["retired"])

        # Leaving retired out keeps it retired (older clients).
        body.pop("retired")
        body["description"] = "edited"
        self._post(path, body)
        experimental.refresh_from_db()
        self.assertTrue(experimental.retired)
