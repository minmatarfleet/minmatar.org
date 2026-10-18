"""Shared EveType name resolution and loading (eveonline.helpers.universe).

The ``_old_*`` functions are verbatim copies of the code each migrated call
site used before, kept here as parity references.
"""

import ast
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from eveuniverse.models import EveCategory, EveGroup, EveType

from eveonline.helpers.universe import (
    ensure_eve_types,
    resolve_types_by_name,
    type_ids_by_name,
)

BACKEND = Path(__file__).resolve().parents[3]


def _old_buyback_resolve(names):
    """buyback.helpers.classify.resolve_types_by_name before the move."""
    if not names:
        return {}
    unique = list(dict.fromkeys(names))
    found = {}
    for eve_type in EveType.objects.filter(name__in=unique).select_related(
        "eve_group", "eve_group__eve_category"
    ):
        found[eve_type.name] = eve_type
    result = {}
    for name in unique:
        if name in found:
            result[name] = found[name]
            continue
        result[name] = (
            EveType.objects.filter(name__iexact=name)
            .select_related("eve_group", "eve_group__eve_category")
            .first()
        )
    return result


def _old_name_map(names):
    """sell_order_health / compressed_ore: ``{t.name: t for t in ...}``."""
    return {t.name: t for t in EveType.objects.filter(name__in=names)}


def _old_values_map(names):
    """buyback.helpers.demand: ``dict(values_list("name", "id"))``."""
    return dict(
        EveType.objects.filter(name__in=names).values_list("name", "id")
    )


def _old_first(name):
    """buyback.helpers.valuation: one ``.filter(name=...).first()`` per row."""
    return EveType.objects.filter(name=name).first()


class UniverseFixtureMixin:
    def setUp(self):
        category = EveCategory.objects.create(
            id=9001, name="Test Category", published=True
        )
        group = EveGroup.objects.create(
            id=9101, name="Test Group", eve_category=category, published=True
        )

        def make(type_id, name, published=True):
            return EveType.objects.create(
                id=type_id, name=name, eve_group=group, published=published
            )

        make(34, "Tritanium")
        make(35, "Pyerite")
        # Published row has the lower id (SDE: Infiltrator II 2175/60376).
        make(2175, "Infiltrator II")
        make(60376, "Infiltrator II", published=False)
        # Published row has the higher id (SDE: DSHR-01H filament).
        make(85282, "Storm Filament", published=False)
        make(90703, "Storm Filament")
        # Both published (SDE: SKIN / booster reissues).
        make(39584, "Brutix Serpentis SKIN")
        make(42177, "Brutix Serpentis SKIN")
        # Both unpublished (SDE: the diamond NPC hulls).
        make(43605, "Diamond Apocalypse", published=False)
        make(45056, "Diamond Apocalypse", published=False)
        # Only an unpublished row.
        make(70001, "Unreleased Gizmo", published=False)

    UNIQUE = ["Tritanium", "Pyerite", "Unreleased Gizmo", "Unknown Thing"]
    DUPLICATES = {
        "Infiltrator II": 2175,
        "Storm Filament": 90703,
        "Brutix Serpentis SKIN": 39584,
        "Diamond Apocalypse": 43605,
    }


class ResolveTypesByNameTest(UniverseFixtureMixin, TestCase):
    def test_exact_names_resolve_and_unknown_names_map_to_none(self):
        result = resolve_types_by_name(["Tritanium", "Nope", "Tritanium"])
        self.assertEqual(list(result), ["Tritanium", "Nope"])
        self.assertEqual(result["Tritanium"].id, 34)
        self.assertIsNone(result["Nope"])

    def test_empty_input(self):
        self.assertEqual(resolve_types_by_name([]), {})
        self.assertEqual(resolve_types_by_name(iter(())), {})

    def test_case_variant_needs_case_insensitive(self):
        self.assertIsNone(resolve_types_by_name(["tritanium"])["tritanium"])
        result = resolve_types_by_name(["tritanium"], case_insensitive=True)
        self.assertEqual(result["tritanium"].id, 34)

    def test_case_insensitive_collision_prefers_published_then_lowest_id(
        self,
    ):
        result = resolve_types_by_name(
            ["infiltrator ii", "storm filament", "diamond apocalypse"],
            case_insensitive=True,
        )
        self.assertEqual(result["infiltrator ii"].id, 2175)
        self.assertEqual(result["storm filament"].id, 90703)
        self.assertEqual(result["diamond apocalypse"].id, 43605)

    def test_duplicate_names_prefer_published_then_lowest_id(self):
        result = resolve_types_by_name(list(self.DUPLICATES))
        self.assertEqual(
            {name: t.id for name, t in result.items()}, self.DUPLICATES
        )

    def test_published_filter(self):
        published = resolve_types_by_name(
            ["Unreleased Gizmo", "Storm Filament"], published=True
        )
        self.assertIsNone(published["Unreleased Gizmo"])
        self.assertEqual(published["Storm Filament"].id, 90703)
        unpublished = resolve_types_by_name(
            ["Storm Filament", "Infiltrator II"], published=False
        )
        self.assertEqual(unpublished["Storm Filament"].id, 85282)
        self.assertEqual(unpublished["Infiltrator II"].id, 60376)

    def test_published_filter_applies_to_case_insensitive_retry(self):
        result = resolve_types_by_name(
            ["unreleased gizmo"], case_insensitive=True, published=True
        )
        self.assertIsNone(result["unreleased gizmo"])

    def test_group_and_category_are_loaded(self):
        eve_type = resolve_types_by_name(["Tritanium"])["Tritanium"]
        with self.assertNumQueries(0):
            self.assertEqual(eve_type.eve_group.eve_category_id, 9001)


class TypeIdsByNameTest(UniverseFixtureMixin, TestCase):
    def test_unknown_names_are_left_out(self):
        self.assertEqual(
            type_ids_by_name(["Tritanium", "Nope"]), {"Tritanium": 34}
        )

    def test_case_insensitive_and_published(self):
        self.assertEqual(type_ids_by_name(["pyerite"]), {})
        self.assertEqual(
            type_ids_by_name(["pyerite"], case_insensitive=True),
            {"pyerite": 35},
        )
        self.assertEqual(
            type_ids_by_name(["Unreleased Gizmo"], published=True), {}
        )

    def test_duplicates_match_resolve_types_by_name(self):
        self.assertEqual(type_ids_by_name(self.DUPLICATES), self.DUPLICATES)

    def test_one_query_for_exact_names(self):
        with self.assertNumQueries(1):
            type_ids_by_name(["Tritanium", "Pyerite", "Nope"])


class CallSiteParityTest(UniverseFixtureMixin, TestCase):
    """Old vs new output per migrated call site on the same fixtures.

    Names that are unique, case variants and unknown names match exactly.
    Duplicate names are the only (intended) difference, pinned below.
    """

    def test_buyback_resolver_parity(self):
        names = self.UNIQUE + ["tritanium", "PYERITE", "unknown thing"]
        old = _old_buyback_resolve(names)
        new = resolve_types_by_name(names, case_insensitive=True)
        self.assertEqual(
            {k: v and v.id for k, v in old.items()},
            {k: v and v.id for k, v in new.items()},
        )

    def test_name_map_parity(self):
        names = self.UNIQUE + ["tritanium"]
        old = {k: v.id for k, v in _old_name_map(names).items()}
        new = {
            k: v.id
            for k, v in resolve_types_by_name(names).items()
            if v is not None
        }
        self.assertEqual(old, new)

    def test_values_map_parity(self):
        names = self.UNIQUE + ["tritanium"]
        self.assertEqual(_old_values_map(names), type_ids_by_name(names))

    def test_first_parity(self):
        for name in self.UNIQUE + ["Infiltrator II", "Brutix Serpentis SKIN"]:
            old = _old_first(name)
            new = resolve_types_by_name([name])[name]
            self.assertEqual(old and old.id, new and new.id, name)

    def test_duplicate_names_old_vs_new(self):
        """The old dict comprehensions kept the last row the DB returned.

        On sqlite and MySQL that is the highest id, which picked the
        unpublished Infiltrator II. ``.first()`` kept the lowest id, which
        picked the unpublished Storm Filament.
        """
        names = list(self.DUPLICATES)
        old_last = {k: v.id for k, v in _old_name_map(names).items()}
        old_first = {name: _old_first(name).id for name in names}
        self.assertEqual(old_last["Infiltrator II"], 60376)
        self.assertEqual(old_first["Storm Filament"], 85282)
        new = type_ids_by_name(names)
        self.assertEqual(new, self.DUPLICATES)


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


class ImportBoundaryTest(TestCase):
    """market and industry resolve names without importing buyback."""

    def test_market_and_industry_do_not_import_buyback_classify(self):
        offenders = []
        for app in ("market", "industry"):
            for path in (BACKEND / app).rglob("*.py"):
                if "tests" in path.parts or path.name.startswith("test"):
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.ImportFrom)
                        and node.module == "buyback.helpers.classify"
                    ):
                        offenders.append(str(path.relative_to(BACKEND)))
        self.assertEqual(offenders, [])
