"""Shared EveType loading (eveonline.helpers.universe)."""

from unittest.mock import patch

from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from eveonline.helpers.universe import ensure_eve_types


class EnsureEveTypesTest(TestCase):
    def setUp(self):
        category = EveCategory.objects.create(
            id=9002, name="Cat", published=True
        )
        group = EveGroup.objects.create(
            id=9102, name="Grp", eve_category=category, published=True
        )
        self.stored = EveType.objects.create(
            id=34, name="Tritanium", eve_group=group, published=True
        )

    @patch.object(EveType.objects, "get_or_create_esi")
    def test_stored_types_need_no_esi(self, esi):
        self.assertEqual(
            ensure_eve_types([34, 34, 0, None]), {34: self.stored}
        )
        esi.assert_not_called()

    @patch.object(EveType.objects, "get_or_create_esi")
    def test_missing_types_are_skipped_when_live_esi_is_off(self, esi):
        self.assertEqual(ensure_eve_types([34, 35]), {34: self.stored})
        self.assertEqual(
            ensure_eve_types([34, 35], raise_on_error=True), {34: self.stored}
        )
        esi.assert_not_called()

    @patch("eveonline.helpers.universe.live_esi_allowed", return_value=True)
    @patch.object(EveType.objects, "get_or_create_esi")
    def test_missing_types_load_from_esi(self, esi, live_esi):
        loaded = EveType(id=35, name="Pyerite")
        esi.return_value = (loaded, True)
        self.assertEqual(
            ensure_eve_types({34, 35}), {34: self.stored, 35: loaded}
        )
        esi.assert_called_once_with(id=35)

    @patch("eveonline.helpers.universe.live_esi_allowed", return_value=True)
    @patch.object(EveType.objects, "get_or_create_esi")
    def test_esi_failure_logs_or_raises(self, esi, live_esi):
        esi.side_effect = RuntimeError("esi down")
        with self.assertLogs("eveonline.helpers.universe", "WARNING"):
            self.assertEqual(ensure_eve_types([34, 35, 36]), {34: self.stored})
        self.assertEqual(esi.call_count, 2)
        with self.assertRaises(RuntimeError):
            ensure_eve_types([35], raise_on_error=True)
