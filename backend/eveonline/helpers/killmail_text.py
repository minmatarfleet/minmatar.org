"""Read and write the attackers/items text on EveCharacterKillmail.

Rows written before October 2026 hold ``str(list)``: Python repr, with
single quotes, ``None`` and ``True``. New rows hold JSON. Readers call
``parse_killmail_list`` and get a list either way, so the two formats can
live side by side until ``convert_killmail_text_to_json`` has rewritten the
old rows.
"""

from __future__ import annotations

import ast
import json
from typing import Any

# A killmail's items list is a few KB; a huge string is not one of ours and
# would make literal_eval slow and memory hungry.
MAX_LITERAL_CHARS = 2_000_000
_EMPTY_TEXT = {"", "None", "null"}
_NOT_JSON = object()


def dump_killmail_list(value: Any) -> str:
    """JSON text for a list of attackers or items (None -> ``[]``)."""
    return json.dumps(value if value is not None else [], default=str)


def _literal(text: str):
    if len(text) > MAX_LITERAL_CHARS:
        return None
    try:
        return ast.literal_eval(text)
    except (
        ValueError,
        SyntaxError,
        TypeError,
        MemoryError,
        RecursionError,
    ):
        return None


def _json(text: str):
    """Decoded JSON, or a sentinel for text that is not JSON."""
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        return _NOT_JSON


def load_killmail_list(value: Any) -> list | None:
    """The stored list, or None when the text is neither JSON nor a repr."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text in _EMPTY_TEXT:
        return []
    parsed = _json(text)
    if parsed is _NOT_JSON:
        parsed = _literal(text)
    return parsed if isinstance(parsed, list) else None


def parse_killmail_list(value: Any) -> list:
    """The stored list, or ``[]`` for text that cannot be read."""
    parsed = load_killmail_list(value)
    return parsed if parsed is not None else []


def is_json_list_text(value: Any) -> bool:
    """True when the text is already a JSON list (nothing to convert)."""
    if not isinstance(value, str):
        return False
    return isinstance(_json(value), list)


def repr_to_json_text(value: Any) -> str | None:
    """JSON text for an old repr row; None when there is nothing to do.

    Returns None for rows that are already JSON and for rows that cannot
    be parsed, which are left exactly as they are.
    """
    if is_json_list_text(value):
        return None
    parsed = load_killmail_list(value)
    if parsed is None:
        return None
    return dump_killmail_list(parsed)


def json_to_repr_text(value: Any) -> str | None:
    """The old ``str(list)`` text for a JSON row (the reverse step)."""
    if not is_json_list_text(value):
        return None
    return str(json.loads(value))
