# pylint: disable=protected-access
from django.contrib import admin
from django.test import SimpleTestCase

from app.admin_standards import (
    LARGE_TABLES,
    READ_ONLY_MODELS,
    ReadOnlyAdminMixin,
    apply_admin_standards,
    model_key,
    unbounded_fk_fields,
)


class AdminStandardsTestCase(SimpleTestCase):
    def setUp(self):
        apply_admin_standards()

    def test_every_admin_has_columns_and_search(self):
        for model, model_admin in admin.site._registry.items():
            label = model_key(model)
            with self.subTest(model=label):
                self.assertNotEqual(
                    tuple(model_admin.list_display), ("__str__",), label
                )
                self.assertTrue(model_admin.search_fields, label)

    def test_no_unbounded_fk_widgets_on_large_models(self):
        for model, model_admin in admin.site._registry.items():
            label = model_key(model)
            with self.subTest(model=label):
                self.assertEqual(unbounded_fk_fields(model_admin), [], label)
                for inline in model_admin.inlines or ():
                    self.assertEqual(
                        unbounded_fk_fields(inline), [], f"{label} inline"
                    )

    def test_logs_and_rollups_are_view_only(self):
        seen = 0
        for model, model_admin in admin.site._registry.items():
            if model_key(model) not in READ_ONLY_MODELS:
                continue
            seen += 1
            with self.subTest(model=model_key(model)):
                self.assertIsInstance(model_admin, ReadOnlyAdminMixin)
                self.assertFalse(model_admin.has_add_permission(None))
                self.assertFalse(model_admin.has_change_permission(None))
                self.assertFalse(model_admin.has_delete_permission(None))
        self.assertGreater(seen, 40)

    def test_large_tables_skip_full_count(self):
        for model, model_admin in admin.site._registry.items():
            if model_key(model) in LARGE_TABLES:
                with self.subTest(model=model_key(model)):
                    self.assertFalse(model_admin.show_full_result_count)
