"""Every setting product code reads must be defined by the settings files.

A setting that only exists in someone's local settings.py silently falls
back to a getattr default in production. This scans product code for
settings.X and getattr(settings, "X") and checks each name is defined by
Django's defaults, the shared settings modules or settings.py.example.
"""

import ast
from pathlib import Path

from django.conf import global_settings
from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"migrations", "tests", "scripts", "node_modules", ".venv"}
SHARED_SETTINGS = (
    "app/settings_common.py",
    "app/settings_celery.py",
    "app/settings_env.py",
    "app/settings.py.example",
)
# Test-only switches, read with a getattr default that is right for
# production.
TEST_ONLY = {
    "TESTING",
    "ALLOW_LIVE_DISCORD_IN_TESTS",
    "ALLOW_LIVE_ESI_IN_TESTS",
    "CELERY_TASK_ALWAYS_EAGER",
    "CELERY_TASK_EAGER_PROPAGATES",
}


def _is_product_module(path: Path) -> bool:
    rel = path.relative_to(BACKEND)
    if SKIP_DIRS & set(rel.parts[:-1]):
        return False
    name = rel.name
    return not (
        name.startswith("test")
        or name.startswith("tests_")
        or name.startswith("settings")
    )


def _defined_names() -> set[str]:
    names = {n for n in dir(global_settings) if n.isupper()}
    for rel in SHARED_SETTINGS:
        tree = ast.parse((BACKEND / rel).read_text())
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    names.add(target.id)
    return names


def _read_names(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "settings"
            and node.attr.isupper()
        ):
            names.add(node.attr)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("getattr", "hasattr")
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "settings"
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            names.add(node.args[1].value)
    return names


class SettingsDefinedTestCase(SimpleTestCase):
    def test_every_setting_read_in_product_code_is_defined(self):
        defined = _defined_names() | TEST_ONLY
        missing = {}
        for path in BACKEND.rglob("*.py"):
            if not _is_product_module(path):
                continue
            source = path.read_text()
            if "django.conf import settings" not in source:
                continue
            for name in _read_names(ast.parse(source)) - defined:
                missing.setdefault(name, []).append(
                    str(path.relative_to(BACKEND))
                )
        self.assertEqual({}, missing)
