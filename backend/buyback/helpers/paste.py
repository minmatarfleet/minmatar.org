"""Parse EVE Online inventory / assets / multibuy paste into name + quantity."""

from __future__ import annotations

import re
from dataclasses import dataclass

_QTY_RE = re.compile(
    r"^([\d][\d,\.\s]*)\s*(?:x|×)?\s*$",
    re.IGNORECASE,
)
_HEADER_HINTS = frozenset(
    {
        "item",
        "name",
        "type",
        "quantity",
        "qty",
        "volume",
        "group",
        "category",
        "total",
    }
)


@dataclass(frozen=True)
class PasteLine:
    name: str
    quantity: int
    raw: str


def _parse_quantity(token: str) -> int | None:
    text = (token or "").strip().replace("\u00a0", " ")
    if not text:
        return None
    # Strip trailing units like "m3" / "m³" if someone pastes volume as qty.
    text = re.sub(r"\s*m[³3]\s*$", "", text, flags=re.IGNORECASE)
    match = _QTY_RE.match(text)
    if not match:
        cleaned = text.replace(",", "").replace(" ", "")
        try:
            value = float(cleaned)
        except ValueError:
            return None
        if value <= 0:
            return None
        return int(value)
    cleaned = match.group(1).replace(",", "").replace(" ", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if value <= 0:
        return None
    return int(value)


def _is_header(line: str) -> bool:
    lowered = line.strip().lower()
    if not lowered:
        return True
    tokens = re.split(r"[\t|]+", lowered)
    hits = sum(1 for t in tokens if t.strip() in _HEADER_HINTS)
    return hits >= 2


def parse_eve_paste(paste: str) -> list[PasteLine]:
    """Parse EVE inventory/assets/multibuy paste into name + quantity lines."""
    if not paste or not paste.strip():
        return []

    aggregated: dict[str, int] = {}
    raw_by_name: dict[str, str] = {}

    for raw_line in (
        paste.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ):
        line = raw_line.strip()
        if not line or _is_header(line):
            continue

        name: str | None = None
        quantity: int | None = None

        if "\t" in line or "|" in line:
            parts = [p.strip() for p in re.split(r"[\t|]+", line) if p.strip()]
            if len(parts) >= 2:
                qty = _parse_quantity(parts[1])
                if qty is not None and not _parse_quantity(parts[0]):
                    name, quantity = parts[0], qty
                else:
                    qty0 = _parse_quantity(parts[0])
                    if qty0 is not None:
                        name, quantity = parts[1], qty0
                    elif qty is not None:
                        name, quantity = parts[0], qty
        else:
            m = re.match(
                r"^(?:(\d[\d,]*)\s*[x×]\s*(.+)|(.+?)\s*[x×]\s*(\d[\d,]*))$",
                line,
                re.IGNORECASE,
            )
            if m:
                if m.group(1) and m.group(2):
                    quantity = _parse_quantity(m.group(1))
                    name = m.group(2).strip()
                else:
                    name = m.group(3).strip()
                    quantity = _parse_quantity(m.group(4))
            else:
                m2 = re.match(r"^(.+?)\s+(\d[\d,]*)$", line)
                if m2 and _parse_quantity(m2.group(2)) is not None:
                    name = m2.group(1).strip()
                    quantity = _parse_quantity(m2.group(2))

        if not name or quantity is None or quantity <= 0:
            continue

        aggregated[name] = aggregated.get(name, 0) + quantity
        raw_by_name.setdefault(name, line)

    return [
        PasteLine(name=name, quantity=qty, raw=raw_by_name[name])
        for name, qty in aggregated.items()
    ]
