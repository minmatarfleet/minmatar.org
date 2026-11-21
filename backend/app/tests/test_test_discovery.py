"""Every test module must be discoverable by Django's test runner.

manage.py test (and CI) only finds test*.py files inside packages. A tests
folder without __init__.py is silently skipped, while pytest still
collects it.
"""

import ast
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


def _test_modules():
    for path in BACKEND.rglob("test*.py"):
        rel = path.relative_to(BACKEND)
        if SKIP_DIRS & set(rel.parts) or len(rel.parts) == 1:
            continue
        yield rel, ast.parse(path.read_text(encoding="utf-8"))


def _classes_with_tests(module: str) -> set[str]:
    """Classes in a backend module that define test methods themselves."""
    path = BACKEND.joinpath(*module.split(".")).with_suffix(".py")
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(item, ast.FunctionDef) and item.name.startswith("test")
            for item in node.body
        )
    }


class TestModuleHygieneTestCase(SimpleTestCase):
    def test_test_classes_are_not_imported_by_name(self):
        """
        A TestCase imported by name into another test module is collected
        there too, so all its tests run twice. Import the module instead
        (`from app.tests import test_x` and subclass `test_x.XTestCase`).
        """
        found = []
        for rel, tree in _test_modules():
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                with_tests = _classes_with_tests(node.module)
                for alias in node.names:
                    if alias.name in with_tests:
                        found.append(f"{rel}: {node.module}.{alias.name}")
        self.assertEqual([], sorted(found))

    def test_migration_tests_are_tagged(self):
        """
        Tests that drive MigrationExecutor re-render the whole migration
        graph and take seconds each. CI runs them as their own job
        (`--tag migration`), so they must carry @tag("migration").
        """
        untagged = []
        for rel, tree in _test_modules():
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                uses_executor = any(
                    isinstance(name, ast.Name)
                    and name.id == "MigrationExecutor"
                    for name in ast.walk(node)
                )
                if not uses_executor:
                    continue
                tags = [
                    arg.value
                    for dec in node.decorator_list
                    if isinstance(dec, ast.Call)
                    and getattr(dec.func, "id", "") == "tag"
                    for arg in dec.args
                    if isinstance(arg, ast.Constant)
                ]
                if "migration" not in tags:
                    untagged.append(f"{rel}: {node.name}")
        self.assertEqual([], sorted(untagged))
