from django.contrib.auth import get_user_model
from django.test import TestCase

from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointPriceHistory,
)

User = get_user_model()
TLIB_CORP_ID = 1000182


class LpPriceHistorySaveTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lp-price", password="x")
        self.currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        IndustryLoyaltyPointPriceHistory.objects.filter(
            loyalty_point=self.currency
        ).delete()
        self.account = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="Alliance pot",
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
            isk_per_lp=840,
        )

    def test_create_does_not_write_history(self):
        self.assertEqual(IndustryLoyaltyPointPriceHistory.objects.count(), 0)

    def test_currency_price_change_writes_history(self):
        self.currency.history_changed_by = self.user
        self.currency.default_isk_per_lp = 900
        self.currency.save()

        row = IndustryLoyaltyPointPriceHistory.objects.get()
        self.assertIsNone(row.account_id)
        self.assertEqual(row.loyalty_point_id, self.currency.pk)
        self.assertEqual(row.old_isk_per_lp, 800)
        self.assertEqual(row.new_isk_per_lp, 900)
        self.assertEqual(row.changed_by_id, self.user.pk)

    def test_currency_unchanged_price_skips_history(self):
        self.currency.name = "TLIB renamed"
        self.currency.save()
        self.assertEqual(IndustryLoyaltyPointPriceHistory.objects.count(), 0)

        self.currency.default_isk_per_lp = 800
        self.currency.save()
        self.assertEqual(IndustryLoyaltyPointPriceHistory.objects.count(), 0)

    def test_currency_update_fields_without_price_skips_history(self):
        self.currency.default_isk_per_lp = 950
        self.currency.save(update_fields=["notes"])
        self.currency.refresh_from_db()
        self.assertEqual(self.currency.default_isk_per_lp, 800)
        self.assertEqual(IndustryLoyaltyPointPriceHistory.objects.count(), 0)

    def test_account_offer_change_writes_history(self):
        self.account.history_changed_by = self.user
        self.account.isk_per_lp = 860
        self.account.save()

        row = IndustryLoyaltyPointPriceHistory.objects.get()
        self.assertEqual(row.account_id, self.account.pk)
        self.assertEqual(row.loyalty_point_id, self.currency.pk)
        self.assertEqual(row.old_isk_per_lp, 840)
        self.assertEqual(row.new_isk_per_lp, 860)
        self.assertEqual(row.changed_by_id, self.user.pk)

    def test_account_unchanged_offer_skips_history(self):
        self.account.notes = "noop"
        self.account.save()
        self.assertEqual(IndustryLoyaltyPointPriceHistory.objects.count(), 0)

    def test_account_offer_cleared_writes_null_new_price(self):
        self.account.isk_per_lp = None
        self.account.save()

        row = IndustryLoyaltyPointPriceHistory.objects.get()
        self.assertEqual(row.old_isk_per_lp, 840)
        self.assertIsNone(row.new_isk_per_lp)
