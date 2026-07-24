from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from industry.helpers.guide_order_summary_export import (
    GuideOrderRow,
    render_typescript_module,
    write_frontend_module,
)


class GuideOrderSummaryExportTest(SimpleTestCase):
    def test_render_typescript_module_includes_rows_and_assumptions(self):
        rows = [
            GuideOrderRow(
                name="Coercer",
                type_id=16236,
                kind="T1",
                faction="T1",
                isk_per_lp=None,
                cost_per=1_047_349,
                jita_sell=1_386_000,
                profit_per=338_651,
                order_profit=33_865_146,
            ),
            GuideOrderRow(
                name="Talwar Fleet Issue",
                type_id=91858,
                kind="Navy",
                faction="Minmatar",
                isk_per_lp=850,
                cost_per=15_748_217,
                jita_sell=19_522_645,
                profit_per=3_774_428,
                order_profit=377_442_795,
                note="BOM proxied (identical navy destroyer recipe)",
            ),
        ]
        text = render_typescript_module(rows, as_of=date(2026, 7, 22))
        self.assertIn("export const AS_OF_DATE = '22 Jul 2026'", text)
        self.assertIn("name: 'Coercer'", text)
        self.assertIn("typeId: 91858", text)
        self.assertIn(
            "note: 'BOM proxied (identical navy destroyer recipe)'", text
        )
        self.assertIn("${ORDER_QTY}", text)
        self.assertIn(
            "pipenv run python manage.py export_guide_order_summary", text
        )

    def test_write_frontend_module(self):
        rows = [
            GuideOrderRow(
                name="Stabber",
                type_id=622,
                kind="T1",
                faction="T1",
                isk_per_lp=None,
                cost_per=1,
                jita_sell=2,
                profit_per=1,
                order_profit=100,
            )
        ]
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "guide-order-summary.ts"
            written = write_frontend_module(
                rows, path=path, as_of=date(2026, 1, 5)
            )
            self.assertEqual(written, path)
            content = path.read_text(encoding="utf-8")
            self.assertIn("name: 'Stabber'", content)
            self.assertIn("AS_OF_DATE = '5 Jan 2026'", content)
