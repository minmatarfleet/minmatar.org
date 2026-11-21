"""Who can dock at a location (EveLocation.dock_access).

An empty list means anyone in the alliance. Otherwise each entry names a
corporation or an alliance; a character docks when its corporation or its
alliance is listed. Names resolve against the local EveCorporation and
EveAlliance tables only, so nothing here calls ESI."""

from typing import Iterable, List, Optional, Tuple

from eveonline.models import EveAlliance, EveCorporation

KIND_CORPORATION = "corporation"
KIND_ALLIANCE = "alliance"


def _entry(kind: str, entity_id: int, name: str, ticker: str) -> dict:
    return {
        "kind": kind,
        "id": int(entity_id),
        "name": name or "",
        "ticker": ticker or "",
    }


def resolve_dock_name(text: str) -> Optional[dict]:
    """A corporation or alliance by name or ticker, or None."""
    value = (text or "").strip()
    if not value:
        return None
    for field in ("name__iexact", "ticker__iexact"):
        corp = EveCorporation.objects.filter(**{field: value}).first()
        if corp is not None:
            return _entry(
                KIND_CORPORATION,
                corp.corporation_id,
                corp.name,
                corp.ticker or "",
            )
        alliance = EveAlliance.objects.filter(**{field: value}).first()
        if alliance is not None:
            return _entry(
                KIND_ALLIANCE,
                alliance.alliance_id,
                alliance.name,
                alliance.ticker,
            )
    return None


def resolve_dock_names(
    names: Iterable[str],
) -> Tuple[List[dict], List[str]]:
    """(entries, unknown names). Duplicates are dropped."""
    entries: List[dict] = []
    unknown: List[str] = []
    seen = set()
    for name in names:
        if not (name or "").strip():
            continue
        entry = resolve_dock_name(name)
        if entry is None:
            unknown.append(name.strip())
            continue
        key = (entry["kind"], entry["id"])
        if key not in seen:
            seen.add(key)
            entries.append(entry)
    return entries, unknown


def dock_entries(location) -> List[dict]:
    """Stored entries, skipping anything malformed."""
    out = []
    for row in getattr(location, "dock_access", None) or []:
        if not isinstance(row, dict):
            continue
        if row.get("kind") not in (KIND_CORPORATION, KIND_ALLIANCE):
            continue
        try:
            entity_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        out.append(
            _entry(
                row["kind"],
                entity_id,
                str(row.get("name") or ""),
                str(row.get("ticker") or ""),
            )
        )
    return out


def same_entries(left: List[dict], right: List[dict]) -> bool:
    def key(rows):
        return sorted((row["kind"], row["id"]) for row in rows)

    return key(left) == key(right)


def is_restricted(location) -> bool:
    return bool(dock_entries(location))


def dock_tickers_of(entries: List[dict]) -> List[str]:
    """Tickers (or names when a ticker is unknown)."""
    return [entry["ticker"] or entry["name"] for entry in entries]


def dock_tickers(location) -> List[str]:
    """Tickers of who can dock; empty when anyone in the alliance can."""
    return dock_tickers_of(dock_entries(location))


def character_can_dock(location, character) -> bool:
    entries = dock_entries(location)
    if not entries:
        return True
    corporation_id = getattr(character, "corporation_id", None)
    alliance_id = getattr(character, "alliance_id", None)
    for entry in entries:
        if (
            entry["kind"] == KIND_CORPORATION
            and corporation_id is not None
            and int(corporation_id) == entry["id"]
        ):
            return True
        if (
            entry["kind"] == KIND_ALLIANCE
            and alliance_id is not None
            and int(alliance_id) == entry["id"]
        ):
            return True
    return False
