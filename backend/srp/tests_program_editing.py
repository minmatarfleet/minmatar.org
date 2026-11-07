from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.test import Client
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from app.testing import make_token
from groups.helpers.feature_access import clear_feature_cache
from srp.models import (
    EveFleetShipReimbursement,
    ShipReimbursementProgram,
    ShipReimbursementProgramAmount,
)
from users.helpers import add_user_permission

BASE = "/api/srp/programs"


class SrpProgramEditingTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=Group, dispatch_uid="group_post_save"
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through, dispatch_uid="user_group_changed"
        )
        super().setUp()
        self.client = Client()
        category = EveCategory.objects.create(
            id=6, name="Ship", published=True
        )
        group = EveGroup.objects.create(
            id=25, name="Frigate", eve_category=category, published=True
        )
        self.ship = EveType.objects.create(
            id=587, name="Rifter", eve_group=group, published=True
        )
        self.program = ShipReimbursementProgram.objects.create(
            eve_type=self.ship
        )
        ShipReimbursementProgramAmount.objects.create(
            program=self.program, srp_value=1_000_000
        )

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {make_token(self.user)}"}

    def _grant(self):
        add_user_permission(self.user, "change_shipreimbursementprogram")
        clear_feature_cache()

    def _grant_view(self):
        add_user_permission(self.user, "view_evefleetshipreimbursement")
        self._grant()

    def _claim(self, status, amount):
        return EveFleetShipReimbursement.objects.create(
            external_killmail_link="x",
            status=status,
            killmail_id=1,
            character_id=1,
            character_name="Pilot",
            primary_character_id=1,
            primary_character_name="Pilot",
            amount=amount,
            ship_name="Rifter",
            ship_type_id=self.ship.id,
        )

    def _post(self, path, body=None):
        return self.client.post(
            f"{BASE}/{path}" if path else BASE,
            body or {},
            content_type="application/json",
            **self._auth(),
        )

    def test_set_amount_requires_permission(self):
        response = self._post(f"{self.program.id}/amount", {"srp_value": 5})
        self.assertEqual(403, response.status_code)
        self.assertEqual(1, self.program.amounts.count())

    def test_set_amount_appends_history(self):
        self._grant()
        response = self._post(
            f"{self.program.id}/amount", {"srp_value": 2_500_000}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(2, self.program.amounts.count())
        latest = self.program.amounts.order_by("-created_at", "-id").first()
        self.assertEqual(2_500_000, latest.srp_value)

    def test_set_amount_rejects_negative_and_unknown(self):
        self._grant()
        negative = self._post(f"{self.program.id}/amount", {"srp_value": -1})
        self.assertEqual(400, negative.status_code)
        unknown = self._post("9999/amount", {"srp_value": 1})
        self.assertEqual(404, unknown.status_code)

    def test_recalculate_requires_permission(self):
        preview = self.client.get(f"{BASE}/recalculate", **self._auth())
        self.assertEqual(403, preview.status_code)
        self.assertEqual(403, self._post("recalculate").status_code)

    def test_preview_then_apply(self):
        self._grant()
        pending = self._claim("pending", 500_000)
        rejected = self._claim("rejected", 500_000)
        preview = self.client.get(f"{BASE}/recalculate", **self._auth())
        self.assertEqual(200, preview.status_code)
        body = preview.json()
        self.assertEqual(1, body["outstanding_count"])
        self.assertEqual(1, body["changed_count"])
        self.assertEqual(500_000, body["current_total"])
        self.assertEqual(1_000_000, body["new_total"])
        pending.refresh_from_db()
        self.assertEqual(500_000, pending.amount)

        applied = self._post("recalculate")
        self.assertEqual(200, applied.status_code)
        self.assertEqual(1, applied.json()["updated"])
        pending.refresh_from_db()
        rejected.refresh_from_db()
        self.assertEqual(1_000_000, pending.amount)
        self.assertEqual(500_000, rejected.amount)

    def test_programs_list_counts_open_and_stale_requests(self):
        self._grant_view()
        self._claim("pending", 500_000)
        self._claim("approved", 1_000_000)
        self._claim("rejected", 500_000)
        response = self.client.get(BASE, **self._auth())
        self.assertEqual(200, response.status_code)
        row = response.json()[0]
        self.assertEqual(2, row["open_requests"])
        self.assertEqual(1, row["stale_requests"])

    def test_hull_preview_lists_only_stale_requests(self):
        self._grant()
        stale = self._claim("pending", 500_000)
        self._claim("pending", 1_000_000)
        preview = self.client.get(
            f"{BASE}/recalculate?ship_type_id={self.ship.id}", **self._auth()
        )
        self.assertEqual(200, preview.status_code)
        body = preview.json()
        self.assertEqual(1, body["outstanding_count"])
        self.assertEqual([stale.id], [c["id"] for c in body["changes"]])
        self.assertEqual(1, body["changes"][0]["character_id"])
        other = self.client.get(
            f"{BASE}/recalculate?ship_type_id=999", **self._auth()
        )
        self.assertEqual(0, other.json()["changed_count"])

    def test_hull_pay_rewrites_only_that_hull(self):
        self._grant()
        stale = self._claim("pending", 500_000)
        other_hull = self._claim("pending", 500_000)
        other_hull.ship_type_id = 999
        other_hull.save()
        applied = self._post(f"recalculate?ship_type_id={self.ship.id}")
        self.assertEqual(200, applied.status_code)
        self.assertEqual(1, applied.json()["updated"])
        stale.refresh_from_db()
        other_hull.refresh_from_db()
        self.assertEqual(1_000_000, stale.amount)
        self.assertEqual(500_000, other_hull.amount)

    def test_keep_filed_amounts_clears_the_stale_count(self):
        self._grant_view()
        stale = self._claim("pending", 500_000)
        kept = self._post(f"recalculate/keep?ship_type_id={self.ship.id}")
        self.assertEqual(200, kept.status_code)
        self.assertEqual(1, kept.json()["updated"])
        stale.refresh_from_db()
        self.assertEqual(500_000, stale.amount)
        row = self.client.get(BASE, **self._auth()).json()[0]
        self.assertEqual(1, row["open_requests"])
        self.assertEqual(0, row["stale_requests"])
        # A new amount makes the kept request stale again.
        self._post(f"{self.program.id}/amount", {"srp_value": 2_000_000})
        row = self.client.get(BASE, **self._auth()).json()[0]
        self.assertEqual(1, row["stale_requests"])

    def test_keep_requires_permission(self):
        response = self._post(f"recalculate/keep?ship_type_id={self.ship.id}")
        self.assertEqual(403, response.status_code)

    def test_add_hull(self):
        self._grant()
        slasher = EveType.objects.create(
            id=585,
            name="Slasher",
            eve_group=self.ship.eve_group,
            published=True,
        )
        response = self._post("", {"eve_type_id": 585, "srp_value": 800_000})
        self.assertEqual(200, response.status_code)
        program = ShipReimbursementProgram.objects.get(eve_type=slasher)
        self.assertEqual(800_000, program.amounts.get().srp_value)
        again = self._post("", {"eve_type_id": 585, "srp_value": 1})
        self.assertEqual(400, again.status_code)

    def test_add_hull_rejects_non_ships_and_needs_permission(self):
        self.assertEqual(
            403,
            self._post("", {"eve_type_id": 587, "srp_value": 1}).status_code,
        )
        self._grant()
        category = EveCategory.objects.create(
            id=4, name="Material", published=True
        )
        group = EveGroup.objects.create(
            id=18, name="Mineral", eve_category=category, published=True
        )
        EveType.objects.create(
            id=34, name="Tritanium", eve_group=group, published=True
        )
        response = self._post("", {"eve_type_id": 34, "srp_value": 1})
        self.assertEqual(400, response.status_code)
