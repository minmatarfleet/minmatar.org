"""Tests for inferred-sales CSV import."""

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
import tempfile

from django.core.management import call_command

from app.test import TestCase
from eveonline.models import EveLocation
from market.helpers.import_inferred_sales_csv import import_inferred_sales_csv
from market.models import EveMarketInferredSale
from market.tests.test_fitting_expectations import _make_eve_type

AMAMAKE_LOCATION_ID = 1022167642188


class ImportInferredSalesCsvTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.location = EveLocation.objects.create(
            location_id=AMAMAKE_LOCATION_ID,
            location_name="Amamake - test",
            solar_system_id=30002537,
            short_name="Amamake",
        )
        self.item = _make_eve_type(438, "Small Focused Pulse Laser I")
        # pylint: disable=consider-using-with
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        self.csv_path = Path(tmpdir.name) / "sample.csv"
        self.csv_path.write_text(
            "\n".join(
                [
                    "location_id,type_id,quantity,price,inferred_at",
                    f"{AMAMAKE_LOCATION_ID},438,10,100.00,2026-06-27T12:00:00Z",
                    f"{AMAMAKE_LOCATION_ID},438,5,110.50,2026-06-28T12:00:00Z",
                    f"{AMAMAKE_LOCATION_ID},99999999,1,1.00,2026-06-27T12:00:00Z",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_import_creates_imported_rows(self):
        result = import_inferred_sales_csv(self.csv_path)
        self.assertEqual(result.read, 3)
        self.assertEqual(result.created, 2)
        self.assertEqual(result.skipped_unknown_type, 1)
        sales = list(
            EveMarketInferredSale.objects.order_by("inferred_at", "quantity")
        )
        self.assertEqual(len(sales), 2)
        self.assertEqual(sales[0].quantity, 10)
        self.assertEqual(sales[0].price, Decimal("100.00"))
        self.assertEqual(
            sales[0].reason, EveMarketInferredSale.REASON_IMPORTED
        )
        self.assertIsNone(sales[0].order_id)
        self.assertEqual(sales[0].location_id, AMAMAKE_LOCATION_ID)

    def test_before_existing_skips_overlap(self):
        EveMarketInferredSale.objects.create(
            location=self.location,
            item=self.item,
            quantity=1,
            price=Decimal("1.00"),
            inferred_at=datetime(2026, 6, 28, 0, 0, 0, tzinfo=dt_timezone.utc),
            reason=EveMarketInferredSale.REASON_PARTIAL_FILL,
        )
        result = import_inferred_sales_csv(self.csv_path)
        self.assertEqual(result.created, 1)
        self.assertEqual(result.skipped_overlap, 1)
        self.assertEqual(EveMarketInferredSale.objects.count(), 2)

    def test_dry_run_writes_nothing(self):
        result = import_inferred_sales_csv(self.csv_path, dry_run=True)
        self.assertEqual(result.created, 2)
        self.assertEqual(EveMarketInferredSale.objects.count(), 0)

    def test_replace_imported(self):
        import_inferred_sales_csv(self.csv_path)
        result = import_inferred_sales_csv(
            self.csv_path,
            replace_imported=True,
            before_existing=False,
        )
        self.assertEqual(result.deleted_imported, 2)
        self.assertEqual(result.created, 2)
        self.assertEqual(
            EveMarketInferredSale.objects.filter(
                reason=EveMarketInferredSale.REASON_IMPORTED
            ).count(),
            2,
        )

    def test_management_command_dry_run(self):
        call_command(
            "import_amamake_inferred_sales",
            csv=str(self.csv_path),
            dry_run=True,
        )
        self.assertEqual(EveMarketInferredSale.objects.count(), 0)
