"""Every test module must be discoverable by Django's test runner.

manage.py test (and CI) only finds test*.py files inside packages. A tests
folder without __init__.py is silently skipped, while pytest still
collects it.
"""

from pathlib import Path

from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"node_modules", ".venv", "venv", "scripts", "static"}


class TestDiscoveryTestCase(SimpleTestCase):
    def test_every_test_module_is_in_a_package(self):
        orphans = []
        for path in BACKEND.rglob("test*.py"):
            rel = path.relative_to(BACKEND)
            if SKIP_DIRS & set(rel.parts) or len(rel.parts) == 1:
                continue
            folder = path.parent
            while folder != BACKEND:
                if not (folder / "__init__.py").exists():
                    orphans.append(str(rel))
                    break
                folder = folder.parent
        self.assertEqual([], sorted(orphans))
