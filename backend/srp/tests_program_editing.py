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
            f"{BASE}/{path}",
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
