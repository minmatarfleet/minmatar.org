from django.test import TestCase

from industry.helpers.lp_ledger import (
    LpLedgerError,
    account_balance,
    post_ledger_entry,
    remaining_lots,
    resolve_offer_isk_per_lp,
    weighted_average_cost_isk_per_lp,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointContact,
)

TLIB_CORP_ID = 1000182


class LpLedgerHelperTestCase(TestCase):
    def setUp(self):
        self.currency, _ = IndustryLoyaltyPoint.objects.update_or_create(
            corporation_id=TLIB_CORP_ID,
            defaults={
                "name": "Tribal Liberation Force",
                "default_isk_per_lp": 800,
                "is_active": True,
            },
        )
        self.stockpile = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="FL33T TLIB pot",
            role=IndustryLoyaltyPointAccount.Role.STOCKPILE,
            isk_per_lp=840,
        )

    def test_resolve_offer_falls_back_to_currency_default(self):
        account = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="No offer set",
            role=IndustryLoyaltyPointAccount.Role.SELLER,
        )
        self.assertEqual(resolve_offer_isk_per_lp(account), 800)
        self.assertEqual(resolve_offer_isk_per_lp(self.stockpile), 840)

    def test_multi_price_credits_and_fifo_average(self):
        post_ledger_entry(self.stockpile, 200_000, 825, notes="order A")
        post_ledger_entry(self.stockpile, 100_000, 850, notes="order B")
        self.assertEqual(account_balance(self.stockpile), 300_000)

        lots = remaining_lots(self.stockpile)
        self.assertEqual(
            [(lot.isk_per_lp, lot.quantity) for lot in lots],
            [(825, 200_000), (850, 100_000)],
        )
        self.assertAlmostEqual(
            weighted_average_cost_isk_per_lp(self.stockpile),
            (200_000 * 825 + 100_000 * 850) / 300_000,
        )

        post_ledger_entry(self.stockpile, -50_000, 840, notes="draw")
        self.assertEqual(account_balance(self.stockpile), 250_000)
        lots = remaining_lots(self.stockpile)
        self.assertEqual(
            [(lot.isk_per_lp, lot.quantity) for lot in lots],
            [(825, 150_000), (850, 100_000)],
        )
        self.assertAlmostEqual(
            weighted_average_cost_isk_per_lp(self.stockpile),
            (150_000 * 825 + 100_000 * 850) / 250_000,
        )

    def test_overdraft_rejected(self):
        post_ledger_entry(self.stockpile, 10_000, 825)
        with self.assertRaises(LpLedgerError):
            post_ledger_entry(self.stockpile, -20_000, 840)
        self.assertEqual(account_balance(self.stockpile), 10_000)

    def test_zero_amount_and_invalid_price_rejected(self):
        with self.assertRaises(LpLedgerError):
            post_ledger_entry(self.stockpile, 0, 825)
        with self.assertRaises(LpLedgerError):
            post_ledger_entry(self.stockpile, 1_000, 0)

    def test_seller_contact_directory_without_balance(self):
        seller = IndustryLoyaltyPointAccount.objects.create(
            loyalty_point=self.currency,
            name="Other militia contact",
            role=IndustryLoyaltyPointAccount.Role.SELLER,
        )
        IndustryLoyaltyPointContact.objects.create(
            account=seller,
            character_name="Amarr Seller",
            discord_username="amarr#0001",
        )
        self.assertEqual(account_balance(seller), 0)
        self.assertEqual(seller.contacts.count(), 1)
        sellers = IndustryLoyaltyPointAccount.objects.filter(
            role=IndustryLoyaltyPointAccount.Role.SELLER,
            loyalty_point=self.currency,
            is_active=True,
        )
        self.assertIn(seller, sellers)
