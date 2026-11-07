"""LP desk Settings endpoints: permissions, writes, price history, audit."""

from django.contrib.auth.models import Permission, User
from django.test import Client

from app.test import TestCase
from app.testing import auth_headers
from audit.models import AuditEntry
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointContact,
    IndustryLoyaltyPointPriceHistory,
)

BASE = "/api/industry/loyalty/settings"


class LoyaltySettingsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        # The TLF row is seeded by a migration.
        self.currency, _ = IndustryLoyaltyPoint.objects.get_or_create(
            corporation_id=1000182,
            defaults={"name": "Tribal Liberation Force"},
        )
        self.currency.default_isk_per_lp = 800
        self.currency.express_isk_per_lp = None
        self.currency.save()
        IndustryLoyaltyPointPriceHistory.objects.all().delete()
        self.manager = User.objects.create(username="lp_manager")
        self.manager.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="industry",
                codename="change_industryloyaltypoint",
            )
        )

    def _call(self, method, path, user, data=None):
        return getattr(self.client, method)(
            f"{BASE}{path}",
            data=data,
            content_type="application/json",
            **auth_headers(user),
        )

    def test_plain_pilot_is_refused(self):
        for method, path, body in (
            ("get", "", {}),
            ("post", "/currencies", {"name": "X", "corporation_id": 5}),
            ("patch", f"/currencies/{self.currency.id}", {}),
            ("post", "/accounts", {"loyalty_point_id": 1, "name": "X"}),
            ("post", "/contacts", {"account_id": 1, "character_name": "X"}),
        ):
            with self.subTest(method=method, path=path):
                response = self._call(method, path, self.user, body)
                self.assertEqual(response.status_code, 403)
        self.assertEqual(AuditEntry.objects.count(), 0)

    def test_manager_reads_corps_with_accounts(self):
        account = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency, name="Seller A"
        )
        IndustryLoyaltyPointContact.objects.create(
            account=account, character_name="Contact A"
        )
        response = self._call("get", "", self.manager)
        self.assertEqual(response.status_code, 200)
        mine = next(c for c in response.json() if c["id"] == self.currency.id)
        self.assertEqual(mine["accounts"][0]["name"], "Seller A")
        self.assertEqual(
            mine["accounts"][0]["contacts"][0]["character_name"],
            "Contact A",
        )

    def test_repricing_writes_history_and_audit(self):
        response = self._call(
            "patch",
            f"/currencies/{self.currency.id}",
            self.manager,
            {"default_isk_per_lp": 850, "express_isk_per_lp": 900},
        )
        self.assertEqual(response.status_code, 200)
        self.currency.refresh_from_db()
        self.assertEqual(self.currency.default_isk_per_lp, 850)
        history = IndustryLoyaltyPointPriceHistory.objects.filter(
            loyalty_point=self.currency
        )
        self.assertEqual(history.count(), 2)
        self.assertTrue(all(h.changed_by == self.manager for h in history))
        entry = AuditEntry.objects.get()
        self.assertEqual(entry.user, self.manager)
        self.assertIn("default_isk_per_lp 800 -> 850", entry.summary)

    def test_disable_corp_and_turn_express_off(self):
        self.currency.express_isk_per_lp = 900
        self.currency.save()
        response = self._call(
            "patch",
            f"/currencies/{self.currency.id}",
            self.manager,
            {"is_active": False, "clear_express": True},
        )
        self.assertEqual(response.status_code, 200)
        self.currency.refresh_from_db()
        self.assertFalse(self.currency.is_active)
        self.assertIsNone(self.currency.express_isk_per_lp)

    def test_duplicate_corp_is_rejected(self):
        response = self._call(
            "post",
            "/currencies",
            self.manager,
            {"name": "Again", "corporation_id": 1000182},
        )
        self.assertEqual(response.status_code, 400)

    def test_account_and_contact_lifecycle(self):
        account = self._call(
            "post",
            "/accounts",
            self.manager,
            {
                "loyalty_point_id": self.currency.id,
                "name": "Stock",
                "role": "stockpile",
            },
        )
        self.assertEqual(account.status_code, 200)
        account_id = account.json()["id"]
        bad_role = self._call(
            "post",
            "/accounts",
            self.manager,
            {
                "loyalty_point_id": self.currency.id,
                "name": "Other",
                "role": "wizard",
            },
        )
        self.assertEqual(bad_role.status_code, 400)
        contact = self._call(
            "post",
            "/contacts",
            self.manager,
            {"account_id": account_id, "character_name": "Pilot One"},
        )
        self.assertEqual(contact.status_code, 200)
        contact_id = contact.json()["id"]
        patched = self._call(
            "patch",
            f"/contacts/{contact_id}",
            self.manager,
            {"is_active": False},
        )
        self.assertFalse(patched.json()["is_active"])
        deleted = self._call("delete", f"/contacts/{contact_id}", self.manager)
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(IndustryLoyaltyPointContact.objects.exists())
        retired = self._call(
            "patch",
            f"/accounts/{account_id}",
            self.manager,
            {"is_active": False},
        )
        self.assertFalse(retired.json()["is_active"])
        self.assertGreaterEqual(AuditEntry.objects.count(), 5)

    def test_list_counts_active_accounts_and_shows_last_change(self):
        IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency, name="On"
        )
        IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency, name="Off", is_active=False
        )
        mine = next(
            c
            for c in self._call("get", "", self.manager).json()
            if c["id"] == self.currency.id
        )
        self.assertEqual(mine["active_account_count"], 1)
        self.assertIsNone(mine["last_change"])

        self._call(
            "patch",
            f"/currencies/{self.currency.id}",
            self.manager,
            {"express_isk_per_lp": 900},
        )
        mine = next(
            c
            for c in self._call("get", "", self.manager).json()
            if c["id"] == self.currency.id
        )
        self.assertEqual(mine["last_change"]["tier"], "express")
        self.assertEqual(mine["last_change"]["new_isk_per_lp"], 900)
        self.assertEqual(mine["last_change"]["changed_by"], "lp_manager")

    def test_history_lists_changes_newest_first(self):
        path = f"/currencies/{self.currency.id}/history"
        self.assertEqual(self._call("get", path, self.user).status_code, 403)
        self.assertEqual(
            self._call(
                "get", "/currencies/999999/history", self.manager
            ).status_code,
            404,
        )
        for price in (810, 820):
            self._call(
                "patch",
                f"/currencies/{self.currency.id}",
                self.manager,
                {"default_isk_per_lp": price},
            )
        response = self._call("get", path, self.manager)
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual([r["new_isk_per_lp"] for r in rows], [820, 810])
        self.assertEqual(rows[0]["tier"], "standard")
        self.assertIsNone(rows[0]["account_name"])
