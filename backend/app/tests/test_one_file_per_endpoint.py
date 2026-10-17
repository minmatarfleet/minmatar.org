"""Keep endpoints packages at one route per module.

``.claude/rules/one-file-per-endpoint.md``: in an ``endpoints`` package each
HTTP method + path gets its own module. The modules listed in
``GROUPED_MODULES`` predate this check and still hold several routes. They
are split when their open feature work settles; until then the list only
shrinks. Splitting one means removing it here, and adding a new grouped
module fails.
"""

import ast
from pathlib import Path
from unittest import TestCase

BACKEND = Path(__file__).resolve().parents[2]

ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "api_operation"}

# Relative to backend/. Remove an entry when its module is split.
GROUPED_MODULES = {
    "campaigns/endpoints/manage.py",
    "campaigns/endpoints/member.py",
    "campaigns/endpoints/projects.py",
    "campaigns/endpoints/public.py",
    "eveonline/endpoints/corporations/get_corp_member_details.py",
    "eveonline/endpoints/corporations/get_corporation_projects.py",
    "surveys/endpoints/manage.py",
    "surveys/endpoints/member.py",
}


def _route_count(path: Path) -> int:
    """Count ``@<router>.<method>(...)`` decorators in one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            func = getattr(decorator, "func", None)
            if (
                isinstance(func, ast.Attribute)
                and func.attr in ROUTE_METHODS
                and isinstance(func.value, ast.Name)
            ):
                count += 1
    return count


def _endpoint_modules():
    for path in sorted(BACKEND.glob("*/endpoints/**/*.py")):
        if "migrations" in path.parts or "tests" in path.parts:
            continue
        yield path.relative_to(BACKEND).as_posix(), path


class OneFilePerEndpointTests(TestCase):
    def test_no_new_module_groups_several_routes(self):
        grouped = {
            name
            for name, path in _endpoint_modules()
            if _route_count(path) > 1
        }
        self.assertEqual(
            sorted(grouped - GROUPED_MODULES),
            [],
            "Give each route its own module in endpoints packages "
            "(see .claude/rules/one-file-per-endpoint.md).",
        )

    def test_split_modules_leave_the_allowlist(self):
        grouped = {
            name
            for name, path in _endpoint_modules()
            if _route_count(path) > 1
        }
        self.assertEqual(
            sorted(GROUPED_MODULES - grouped),
            [],
            "These modules hold one route now; remove them from "
            "GROUPED_MODULES.",
        )

    def test_counts_decorated_routes(self):
        """The scanner must see the routes in a known grouped module."""
        self.assertGreater(
            _route_count(BACKEND / "campaigns/endpoints/public.py"), 1
        )
