"""
Ratchet on broad `except` handlers that swallow errors silently.

A broad handler (`except Exception`, `except BaseException`, bare `except`)
must do one of:

- log (logger.exception / logger.warning(..., exc_info=True) / ...),
- re-raise, retry, or report the error to the caller (ErrorResponse.log,
  admin message_user, management command stderr),
- carry a `# expected: <why>` comment on the `except` line or just inside
  the handler, for legitimate best-effort fallbacks.

SILENT_BASELINE lists the handlers that did none of these when the ratchet was
added, per function. The count may only go down: fix a handler (log it, or
narrow it to the exception you expect) and lower or delete its entry. A new
silent handler fails this test.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parent.parent

BROAD = {"Exception", "BaseException"}
LOG_METHODS = {
    "exception",
    "error",
    "warning",
    "warn",
    "info",
    "debug",
    "critical",
    "log",
}
REPORT_CALLS = {
    "capture_exception",
    "retry",
    "message_user",
    "log_affiliation_update_error",
}
SKIP_DIRS = {"migrations", "tests", "scripts", "node_modules"}

# path::function -> silent handlers allowed there. Only ever lower these.
# Untouched on purpose when the ratchet landed:
# - eveonline/client.py: returns the error to the caller as an EsiResponse
#   (ERROR_CALLING_ESI); the ESI client work owns any change there.
# - surveys/helpers/*: best-effort survey autofill/stats; a failure shows
#   an empty prefill or zero, which the pilot or reviewer corrects.
# - authentication.py, users/router.py: token checks that answer 401; the
#   auth work owns them.
# - the rest: display fallbacks (names, mentions, market volumes) and dev
#   tooling (live_verify, import commands).
SILENT_BASELINE = {
    "authentication.py::AuthBearer.authenticate": 1,
    "buyback/helpers/purchase_discord.py::_user_mention": 1,
    "buyback/management/commands/import_buyback_from_production.py::Command._history_type_ids": 1,  # noqa: E501
    "discord/live_verify.py::LiveVerifyRunner.case_h3": 1,
    "discord/live_verify.py::LiveVerifyRunner.run_case": 1,
    "eveonline/client.py::EsiClient._authenticated_esi_request": 1,
    "eveonline/client.py::EsiClient._cursor_walk": 1,
    "eveonline/client.py::EsiClient._paginated_corporation_get": 2,
    "eveonline/client.py::EsiClient._valid_token": 1,
    "eveonline/client.py::EsiClient.get_character_assets": 1,
    "eveonline/client.py::EsiClient.get_character_blueprints": 2,
    "eveonline/client.py::EsiClient.get_character_industry_jobs": 1,
    "eveonline/client.py::EsiClient.get_character_skills": 1,
    "eveonline/client.py::EsiClient.get_corporation_blueprints": 2,
    "eveonline/client.py::EsiClient.get_corporation_industry_jobs": 2,
    "eveonline/client.py::EsiClient.get_corporation_roles": 2,
    "eveonline/client.py::EsiClient.get_corporation_wallet_journal_all_divisions": 1,  # noqa: E501
    "eveonline/client.py::EsiClient.get_corporation_wallet_transactions": 1,
    "eveonline/client.py::EsiClient.get_corporation_wallets": 1,
    "eveonline/helpers/corporation_contract_display.py::acceptor_display": 1,
    "eveonline/helpers/corporation_contract_display.py::display_character": 1,
    "industry/helpers/lp_buyback_discord.py::_user_mention": 1,
    "market/helpers/inferred_sales_monthly_volume.py::_enrich_rows": 1,
    "surveys/helpers/autofill.py::_character_ids": 1,
    "surveys/helpers/autofill.py::_corp_context": 1,
    "surveys/helpers/autofill.py::_learning_progress": 2,
    "surveys/helpers/autofill.py::_prime_time": 1,
    "surveys/helpers/autofill.py::_role_flags": 1,
    "surveys/helpers/autofill.py::_tribe_names": 1,
    "surveys/helpers/autofill.py::community_status": 1,
    "surveys/helpers/content.py::_fleet_title": 1,
    "surveys/helpers/content.py::_pc": 1,
    "surveys/helpers/content.py::_training_resources": 1,
    "surveys/helpers/giveback.py::_community_snapshot": 1,
    "surveys/helpers/giveback.py::_doctrines_ready": 1,
    "surveys/helpers/giveback.py::_guides_completed": 1,
    "surveys/helpers/giveback.py::_primary_tribe": 1,
    "surveys/helpers/giveback.py::_srp_received": 1,
    "surveys/helpers/teams.py::_chief": 1,
    "surveys/helpers/tenure.py::member_join_date": 1,
    "surveys/helpers/usage.py::_char_ids": 1,
    "surveys/helpers/usage.py::_used_buyback": 1,
    "surveys/helpers/usage.py::_used_freight": 1,
    "surveys/helpers/usage.py::_used_loyalty": 1,
    "surveys/helpers/usage.py::_used_market": 1,
    "surveys/helpers/usage.py::_used_orders": 1,
    "surveys/helpers/usage.py::_used_srp": 1,
    "users/router.py::get_session": 1,
}


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    types = (
        handler.type.elts
        if isinstance(handler.type, ast.Tuple)
        else [handler.type]
    )
    for node in types:
        name = (
            node.id
            if isinstance(node, ast.Name)
            else node.attr if isinstance(node, ast.Attribute) else ""
        )
        if name in BROAD:
            return True
    return False


def _call_name(func: ast.expr) -> tuple[str, str]:
    """(receiver, name) for `receiver.name(...)` or ("", name)."""
    if isinstance(func, ast.Attribute):
        value = func.value
        receiver = (
            value.id
            if isinstance(value, ast.Name)
            else value.attr if isinstance(value, ast.Attribute) else ""
        )
        return receiver, func.attr
    if isinstance(func, ast.Name):
        return "", func.id
    return "", ""


def _reports(handler: ast.ExceptHandler) -> bool:
    body = ast.Module(body=handler.body, type_ignores=[])
    for node in ast.walk(body):
        if isinstance(node, ast.Raise):
            return True
        if not isinstance(node, ast.Call):
            continue
        receiver, name = _call_name(node.func)
        if name in LOG_METHODS and (
            "log" in receiver.lower() or receiver == "ErrorResponse"
        ):
            return True
        if name in REPORT_CALLS:
            return True
        if name == "write" and receiver in ("stderr", "stdout"):
            return True
        if receiver == "messages" and name in ("error", "warning"):
            return True
    return False


def _has_expected_comment(handler: ast.ExceptHandler, lines) -> bool:
    """`# expected:` on the except line or before/on the first body line."""
    first, last = handler.lineno, handler.body[0].lineno
    return any("# expected:" in lines[n - 1] for n in range(first, last + 1))


def _qualnames(tree: ast.AST) -> dict[int, str]:
    """Map each except handler's line to its enclosing function qualname."""
    out: dict[int, str] = {}

    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                visit(child, scope + [child.name])
            else:
                if isinstance(child, ast.ExceptHandler):
                    out[child.lineno] = ".".join(scope) or "<module>"
                visit(child, scope)

    visit(tree, [])
    return out


def silent_handlers() -> list[tuple[str, int]]:
    """(path::function, line) for every silent broad handler."""
    found = []
    for path in sorted(BACKEND.rglob("*.py")):
        rel = path.relative_to(BACKEND)
        if any(
            part in SKIP_DIRS or part.startswith(".") for part in rel.parts
        ):
            continue
        name = rel.name
        if name.startswith("test") or name.endswith("tests.py"):
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines = source.splitlines()
        scopes = _qualnames(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or not _is_broad(node):
                continue
            if _reports(node) or _has_expected_comment(node, lines):
                continue
            found.append(
                (f"{rel.as_posix()}::{scopes[node.lineno]}", node.lineno)
            )
    return found


class SilentExceptRatchetTestCase(SimpleTestCase):
    def test_no_new_silent_broad_excepts(self):
        found = silent_handlers()
        counts = Counter(key for key, _ in found)
        over = []
        for key, count in sorted(counts.items()):
            allowed = SILENT_BASELINE.get(key, 0)
            if count > allowed:
                lines = [str(line) for k, line in found if k == key]
                over.append(
                    f"{key} (line {', '.join(lines)}): {count} silent, "
                    f"{allowed} allowed"
                )
        self.assertEqual(
            [],
            over,
            "Broad except handlers must log, re-raise, or say why with an "
            "`# expected:` comment. See app/test_silent_excepts.py.",
        )

    def test_detector_flags_and_clears_handlers(self):
        tree_src = (
            "def a():\n"
            "    try:\n        x()\n"
            "    except Exception:\n        pass\n"
            "def b():\n"
            "    try:\n        x()\n"
            "    except Exception:\n        logger.exception('x')\n"
            "def c():\n"
            "    try:\n        x()\n"
            "    except Exception:  # expected: optional\n        pass\n"
        )
        tree = ast.parse(tree_src)
        lines = tree_src.splitlines()
        handlers = [
            n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)
        ]
        silent = [
            h.lineno
            for h in handlers
            if not _reports(h) and not _has_expected_comment(h, lines)
        ]
        self.assertEqual([4], silent)
