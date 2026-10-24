"""Recognise and parse what a pilot pastes: a d-scan or a Local member list.

D-scan (Ctrl+A, Ctrl+C in the Directional Scanner) gives one tab-separated
line per object: ``type id, name, type name, distance``. Local's member
list gives one character name per line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_PASTE_CHARS = 200_000
MAX_DSCAN_LINES = 5_000
MAX_LOCAL_NAMES = 1_000

DSCAN = "dscan"
LOCAL = "local"

_DSCAN_LINE = re.compile(r"^(\d+)\t([^\t]*)\t([^\t]+)\t([^\t]*)$")
# EVE character names: 3-37 characters, letters, digits, spaces, ' . -
_CHARACTER_NAME = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9 .'\-]{1,35}[A-Za-z0-9.']$"
)


class PasteError(ValueError):
    pass


@dataclass(frozen=True)
class DscanLine:
    type_id: int
    name: str
    type_name: str


def _lines(text: str) -> list[str]:
    return [line.strip("\r ") for line in text.split("\n") if line.strip()]


def detect_kind(text: str) -> str | None:
    lines = _lines(text)
    if not lines:
        return None
    dscan = sum(1 for line in lines if _DSCAN_LINE.match(line))
    if dscan and dscan * 2 >= len(lines):
        return DSCAN
    if all(_CHARACTER_NAME.match(line.strip()) for line in lines):
        return LOCAL
    return None


def parse_dscan(text: str) -> list[DscanLine]:
    entries = []
    for line in _lines(text):
        match = _DSCAN_LINE.match(line)
        if not match:
            continue
        entries.append(
            DscanLine(
                type_id=int(match.group(1)),
                name=match.group(2).strip(),
                type_name=match.group(3).strip(),
            )
        )
        if len(entries) > MAX_DSCAN_LINES:
            raise PasteError(
                f"A d-scan can have at most {MAX_DSCAN_LINES} lines."
            )
    if not entries:
        raise PasteError("That doesn't look like a d-scan.")
    return entries


def parse_local(text: str) -> list[str]:
    names: dict[str, str] = {}
    for line in _lines(text):
        name = " ".join(line.split())
        if not _CHARACTER_NAME.match(name):
            continue
        names.setdefault(name.lower(), name)
    if not names:
        raise PasteError("That doesn't look like a Local member list.")
    if len(names) > MAX_LOCAL_NAMES:
        raise PasteError(f"Local can have at most {MAX_LOCAL_NAMES} names.")
    return list(names.values())


def parse(text: str, kind: str | None = None) -> tuple[str, list]:
    """Return ``(kind, entries)``; ``kind`` overrides detection."""
    if not text or not text.strip():
        raise PasteError("The paste is empty.")
    if len(text) > MAX_PASTE_CHARS:
        raise PasteError("The paste is too long.")
    kind = kind or detect_kind(text)
    if kind == DSCAN:
        return kind, parse_dscan(text)
    if kind == LOCAL:
        return kind, parse_local(text)
    raise PasteError("Paste a d-scan or a Local member list.")
