"""docs/auth/feature-catalog.md must list every registered feature."""

import re
import unittest
from pathlib import Path

from groups.features.registry import FEATURE_DEFINITIONS

CATALOG = Path(__file__).resolve().parents[3] / "docs/auth/feature-catalog.md"
ROW = re.compile(
    r"^\| `([a-z_.]+)` \| `([a-z_]+)` \| ([^|]*)\|([^|]*)\|", re.M
)
NO_ON_LEAVE = "no `on_leave` deny"


@unittest.skipUnless(CATALOG.exists(), "needs the full repository checkout")
class FeatureCatalogDocTest(unittest.TestCase):
    def setUp(self):
        text = CATALOG.read_bytes().decode("utf-8")
        self.rows = {match.group(1): match for match in ROW.finditer(text)}

    def test_every_registry_code_has_a_row(self):
        missing = sorted(set(FEATURE_DEFINITIONS) - set(self.rows))
        self.assertEqual(missing, [], "add these to feature-catalog.md")

    def test_no_row_for_an_unknown_code(self):
        unknown = sorted(set(self.rows) - set(FEATURE_DEFINITIONS))
        self.assertEqual(unknown, [])

    def test_rows_match_the_registry(self):
        wrong = []
        for code, definition in FEATURE_DEFINITIONS.items():
            row = self.rows.get(code)
            if row is None:
                continue
            scope, legacy, wiring = row.group(2), row.group(3), row.group(4)
            legacy_permissions = re.findall(r"`([a-z_.]+)`", legacy)
            documented = legacy_permissions[0] if legacy_permissions else ""
            if scope != definition.scope.value:
                wrong.append(f"{code}: scope {scope}")
            if documented != definition.legacy_permission:
                wrong.append(f"{code}: legacy permission {documented!r}")
            denies_on_leave = "on_leave" in definition.deny_community_statuses
            if denies_on_leave == (NO_ON_LEAVE in wiring):
                wrong.append(f"{code}: on_leave note")
        self.assertEqual(wrong, [])
