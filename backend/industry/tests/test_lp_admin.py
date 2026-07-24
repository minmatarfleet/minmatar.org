from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from industry.forms import IndustryLoyaltyPointAccountAdminForm
from industry.helpers.lp_ledger import account_balance, post_ledger_entry
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointLedgerEntry,
)

User = get_user_model()
TLIB_CORP_ID = 1000182


class LpAccountAdminFormTestCase(TestCase):
    def setUp(self):
        self.currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        self.account = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="Alliance pot",
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
            isk_per_lp=840,
        )

    def test_post_credit_via_form(self):
        form = IndustryLoyaltyPointAccountAdminForm(
            data={
                "loyalty_point": self.currency.pk,
                "name": self.account.name,
                "role": self.account.role,
                "isk_per_lp": 840,
                "corporation_name": "",
                "is_active": True,
                "notes": "",
                "ledger_direction": "credit",
                "ledger_quantity": 200000,
                "ledger_isk_per_lp": 825,
                "ledger_notes": "order A",
            },
            instance=self.account,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        entry = form.post_ledger_if_requested()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.amount, 200000)
        self.assertEqual(entry.isk_per_lp, 825)
        self.assertEqual(account_balance(self.account), 200000)

    def test_debit_overdraft_fails_clean(self):
        post_ledger_entry(self.account, 10_000, 825)
        form = IndustryLoyaltyPointAccountAdminForm(
            data={
                "loyalty_point": self.currency.pk,
                "name": self.account.name,
                "role": self.account.role,
                "isk_per_lp": 840,
                "corporation_name": "",
                "is_active": True,
                "notes": "",
                "ledger_direction": "debit",
                "ledger_quantity": 50_000,
                "ledger_isk_per_lp": 840,
                "ledger_notes": "",
            },
            instance=self.account,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("ledger_quantity", form.errors)


class LpAdminViewsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="lp_admin",
            email="lp_admin@example.com",
            password="test",
        )
        self.client.force_login(self.user)
        self.currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        self.account = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="Alliance pot",
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
            isk_per_lp=840,
        )

    def test_loyalty_point_change_page_loads(self):
        url = reverse(
            "admin:industry_industryloyaltypoint_change",
            args=[self.currency.pk],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alliance pot")
        self.assertContains(response, "default_isk_per_lp")

    def test_account_change_page_has_post_ledger_fields(self):
        url = reverse(
            "admin:industry_industryloyaltypointaccount_change",
            args=[self.account.pk],
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Post ledger entry")
        self.assertContains(response, "ledger_quantity")
        self.assertContains(response, "Remaining lots")

    def test_account_post_credit_from_change_view(self):
        url = reverse(
            "admin:industry_industryloyaltypointaccount_change",
            args=[self.account.pk],
        )
        response = self.client.post(
            url,
            {
                "loyalty_point": self.currency.pk,
                "name": self.account.name,
                "role": self.account.role,
                "isk_per_lp": 840,
                "corporation_name": "",
                "is_active": "on",
                "notes": "",
                "ledger_direction": "credit",
                "ledger_quantity": "100000",
                "ledger_isk_per_lp": "850",
                "ledger_notes": "buy order",
                "contacts-TOTAL_FORMS": "0",
                "contacts-INITIAL_FORMS": "0",
                "contacts-MIN_NUM_FORMS": "0",
                "contacts-MAX_NUM_FORMS": "1000",
                "ledger_entries-TOTAL_FORMS": "0",
                "ledger_entries-INITIAL_FORMS": "0",
                "ledger_entries-MIN_NUM_FORMS": "0",
                "ledger_entries-MAX_NUM_FORMS": "1000",
                "_continue": "Save and continue editing",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(account_balance(self.account), 100000)
        entry = IndustryLoyaltyPointLedgerEntry.objects.get(
            account=self.account
        )
        self.assertEqual(entry.amount, 100000)
        self.assertEqual(entry.isk_per_lp, 850)

    def test_ledger_add_page_loads(self):
        url = reverse("admin:industry_industryloyaltypointledgerentry_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Direction")
        self.assertContains(response, "LP quantity")
