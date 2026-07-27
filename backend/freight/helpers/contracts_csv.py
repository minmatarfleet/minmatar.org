"""Build a detailed CSV export of finished freight contracts for tribe leads."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timezone as dt_timezone

from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EveLocation,
)
from freight.helpers.contract_display import (
    FREIGHT_CORP_FALLBACK_NAME,
    completed_by_display,
    display_character,
    freight_corp_display_name,
    resolve_characters,
    resolve_location_names,
)
from freight.models import FREIGHT_CORPORATION_ID, FreightContract

CSV_COLUMNS = (
    "contract_id",
    "status",
    "type",
    "availability",
    "title",
    "for_corporation",
    "start_location_id",
    "start_location_short_name",
    "start_location_full_name",
    "start_solar_system_name",
    "end_location_id",
    "end_location_short_name",
    "end_location_full_name",
    "end_solar_system_name",
    "volume_m3",
    "collateral_isk",
    "reward_isk",
    "price_isk",
    "buyout_isk",
    "days_to_complete",
    "date_issued",
    "date_expired",
    "date_accepted",
    "date_completed",
    "delivery_duration_hours",
    "issuer_character_id",
    "issuer_character_name",
    "issuer_primary_character_id",
    "issuer_primary_character_name",
    "issuer_corporation_id",
    "issuer_corporation_name",
    "issuer_corporation_ticker",
    "issuer_alliance_id",
    "issuer_alliance_name",
    "issuer_alliance_ticker",
    "acceptor_character_id",
    "acceptor_character_name",
    "servicing_primary_character_id",
    "servicing_primary_character_name",
    "servicing_corporation_id",
    "servicing_corporation_name",
    "servicing_corporation_ticker",
    "assignee_id",
    "freight_corporation_id",
    "freight_corporation_name",
    "freight_corporation_ticker",
    "updated_at",
)


def _iso(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt_timezone.utc)
        return value.isoformat()
    return str(value)


def _num(value) -> str:
    if value is None:
        return ""
    return str(value)


def _duration_hours(start, end) -> str:
    if not start or not end:
        return ""
    delta = end - start
    return f"{delta.total_seconds() / 3600:.2f}"


def _corp_map(corporation_ids):
    if not corporation_ids:
        return {}
    return {
        c.corporation_id: c
        for c in EveCorporation.objects.filter(
            corporation_id__in=corporation_ids
        )
    }


def _alliance_map(alliance_ids):
    if not alliance_ids:
        return {}
    return {
        a.alliance_id: a
        for a in EveAlliance.objects.filter(alliance_id__in=alliance_ids)
    }


def _location_details(location_ids):
    if not location_ids:
        return {}
    return {
        loc.location_id: loc
        for loc in EveLocation.objects.filter(location_id__in=location_ids)
    }


def _chars_by_user_id(char_lookup):
    """Bulk map user_id → characters to avoid N+1 in primary fallback."""
    user_ids = set()
    for char in char_lookup.values():
        user = char.user or (
            char.token.user if getattr(char, "token", None) else None
        )
        if user:
            user_ids.add(user.id)
    if not user_ids:
        return {}

    by_user: dict[int, list] = defaultdict(list)
    for char in EveCharacter.objects.filter(user_id__in=user_ids).only(
        "id",
        "character_id",
        "character_name",
        "user_id",
        "corporation_id",
        "alliance_id",
    ):
        by_user[char.user_id].append(char)
    return by_user


def _collect_entity_ids(contracts):
    location_ids = set()
    character_ids = set()
    corporation_ids = set()
    has_freight_corp_acceptor = False

    for contract in contracts:
        if contract.start_location_id:
            location_ids.add(int(contract.start_location_id))
        if contract.end_location_id:
            location_ids.add(int(contract.end_location_id))
        if contract.issuer_id:
            character_ids.add(int(contract.issuer_id))
        if contract.acceptor_id == FREIGHT_CORPORATION_ID:
            has_freight_corp_acceptor = True
        elif contract.acceptor_id:
            character_ids.add(int(contract.acceptor_id))
        if contract.issuer_corporation_id:
            corporation_ids.add(int(contract.issuer_corporation_id))

    return (
        location_ids,
        character_ids,
        corporation_ids,
        has_freight_corp_acceptor,
    )


def _resolve_servicing(
    contract, char_lookup, chars_by_user, freight_corp_name
):
    acceptor_raw = None
    servicing_primary = None
    servicing_name_override = None
    if contract.acceptor_id == FREIGHT_CORPORATION_ID:
        servicing_name_override = (
            freight_corp_name or FREIGHT_CORP_FALLBACK_NAME
        )
    elif contract.acceptor_id:
        acceptor_raw = char_lookup.get(contract.acceptor_id)
        servicing_primary = completed_by_display(
            acceptor_raw, chars_by_user_id=chars_by_user
        )
        if not servicing_primary and contract.acceptor_id:
            # ESI acceptor id known but EveCharacter missing.
            servicing_name_override = ""
    return acceptor_raw, servicing_primary, servicing_name_override


def _add_char_corp_ids(corporation_ids, *chars):
    for display_char in chars:
        if display_char and display_char.corporation_id:
            corporation_ids.add(int(display_char.corporation_id))


def _add_char_alliance_ids(alliance_ids, *chars):
    for display_char in chars:
        if display_char and display_char.alliance_id:
            alliance_ids.add(int(display_char.alliance_id))


def _resolve_contract_parties(
    contracts, char_lookup, chars_by_user, freight_corp_name, corporation_ids
):
    resolved = []
    for contract in contracts:
        start_id = (
            int(contract.start_location_id)
            if contract.start_location_id
            else None
        )
        end_id = (
            int(contract.end_location_id) if contract.end_location_id else None
        )
        issuer_raw = char_lookup.get(contract.issuer_id)
        issuer_primary = display_character(issuer_raw)
        acceptor_raw, servicing_primary, servicing_name_override = (
            _resolve_servicing(
                contract, char_lookup, chars_by_user, freight_corp_name
            )
        )
        _add_char_corp_ids(
            corporation_ids, issuer_primary, servicing_primary, issuer_raw
        )
        resolved.append(
            (
                contract,
                start_id,
                end_id,
                issuer_raw,
                issuer_primary,
                acceptor_raw,
                servicing_primary,
                servicing_name_override,
            )
        )
    return resolved


def _alliance_ids_for_rows(char_lookup, resolved, corps):
    alliance_ids = set()
    for char in char_lookup.values():
        if char.alliance_id:
            alliance_ids.add(int(char.alliance_id))
    for row in resolved:
        _add_char_alliance_ids(alliance_ids, row[3], row[4], row[6])
    for corp in corps.values():
        if corp.alliance_id:
            alliance_ids.add(int(corp.alliance_id))
    return alliance_ids


def _csv_row(
    contract,
    start_id,
    end_id,
    issuer_raw,
    issuer_primary,
    acceptor_raw,
    servicing_primary,
    servicing_name_override,
    *,
    location_short_names,
    location_details,
    corps,
    alliances,
    freight_corp,
    freight_corp_name,
):
    start_loc = location_details.get(start_id) if start_id else None
    end_loc = location_details.get(end_id) if end_id else None

    issuer_corp_id = contract.issuer_corporation_id or (
        issuer_raw.corporation_id if issuer_raw else None
    )
    issuer_corp = corps.get(int(issuer_corp_id)) if issuer_corp_id else None
    issuer_alliance_id = (
        issuer_primary.alliance_id if issuer_primary else None
    ) or (issuer_raw.alliance_id if issuer_raw else None)
    issuer_alliance = (
        alliances.get(int(issuer_alliance_id)) if issuer_alliance_id else None
    )

    servicing_corp_id = (
        servicing_primary.corporation_id if servicing_primary else None
    )
    if contract.acceptor_id == FREIGHT_CORPORATION_ID and freight_corp:
        servicing_corp_id = freight_corp.corporation_id
    servicing_corp = (
        corps.get(int(servicing_corp_id)) if servicing_corp_id else None
    )

    freight_corp_obj = freight_corp
    if contract.corporation_id and not freight_corp_obj:
        freight_corp_obj = EveCorporation.objects.filter(
            pk=contract.corporation_id
        ).first()

    acceptor_is_corp = contract.acceptor_id == FREIGHT_CORPORATION_ID
    servicing_name = (
        servicing_name_override
        if servicing_name_override is not None
        else (servicing_primary.character_name if servicing_primary else "")
    )

    return {
        "contract_id": _num(contract.contract_id),
        "status": contract.status or "",
        "type": contract.type or "",
        "availability": contract.availability or "",
        "title": contract.title or "",
        "for_corporation": ("true" if contract.for_corporation else "false"),
        "start_location_id": _num(start_id),
        "start_location_short_name": (
            location_short_names.get(start_id, "") if start_id else ""
        ),
        "start_location_full_name": (
            start_loc.location_name if start_loc else ""
        ),
        "start_solar_system_name": (
            start_loc.solar_system_name if start_loc else ""
        ),
        "end_location_id": _num(end_id),
        "end_location_short_name": (
            location_short_names.get(end_id, "") if end_id else ""
        ),
        "end_location_full_name": (end_loc.location_name if end_loc else ""),
        "end_solar_system_name": (
            end_loc.solar_system_name if end_loc else ""
        ),
        "volume_m3": _num(contract.volume),
        "collateral_isk": _num(contract.collateral),
        "reward_isk": _num(contract.reward),
        "price_isk": _num(contract.price),
        "buyout_isk": _num(contract.buyout),
        "days_to_complete": _num(contract.days_to_complete),
        "date_issued": _iso(contract.date_issued),
        "date_expired": _iso(contract.date_expired),
        "date_accepted": _iso(contract.date_accepted),
        "date_completed": _iso(contract.date_completed),
        "delivery_duration_hours": _duration_hours(
            contract.date_issued, contract.date_completed
        ),
        "issuer_character_id": _num(contract.issuer_id),
        "issuer_character_name": (
            issuer_raw.character_name if issuer_raw else ""
        ),
        "issuer_primary_character_id": _num(
            issuer_primary.character_id if issuer_primary else None
        ),
        "issuer_primary_character_name": (
            issuer_primary.character_name if issuer_primary else ""
        ),
        "issuer_corporation_id": _num(issuer_corp_id),
        "issuer_corporation_name": (issuer_corp.name if issuer_corp else ""),
        "issuer_corporation_ticker": (
            issuer_corp.ticker if issuer_corp else ""
        ),
        "issuer_alliance_id": _num(issuer_alliance_id),
        "issuer_alliance_name": (
            issuer_alliance.name if issuer_alliance else ""
        ),
        "issuer_alliance_ticker": (
            issuer_alliance.ticker if issuer_alliance else ""
        ),
        "acceptor_character_id": _num(
            None if acceptor_is_corp else contract.acceptor_id
        ),
        "acceptor_character_name": (
            freight_corp_name
            if acceptor_is_corp
            else (acceptor_raw.character_name if acceptor_raw else "")
        ),
        "servicing_primary_character_id": _num(
            None
            if acceptor_is_corp
            else (
                servicing_primary.character_id if servicing_primary else None
            )
        ),
        "servicing_primary_character_name": servicing_name,
        "servicing_corporation_id": _num(servicing_corp_id),
        "servicing_corporation_name": (
            servicing_corp.name if servicing_corp else ""
        ),
        "servicing_corporation_ticker": (
            servicing_corp.ticker if servicing_corp else ""
        ),
        "assignee_id": _num(contract.assignee_id),
        "freight_corporation_id": _num(
            freight_corp_obj.corporation_id
            if freight_corp_obj
            else FREIGHT_CORPORATION_ID
        ),
        "freight_corporation_name": (
            freight_corp_obj.name if freight_corp_obj else ""
        ),
        "freight_corporation_ticker": (
            freight_corp_obj.ticker if freight_corp_obj else ""
        ),
        "updated_at": _iso(contract.updated_at),
    }


def build_freight_history_csv_rows(contracts) -> list[dict[str, str]]:
    """Resolve related entities and return CSV row dicts for finished contracts."""
    (
        location_ids,
        character_ids,
        corporation_ids,
        has_freight_corp_acceptor,
    ) = _collect_entity_ids(contracts)

    location_short_names = resolve_location_names(location_ids)
    location_details = _location_details(location_ids)
    char_lookup = resolve_characters(character_ids)
    chars_by_user = _chars_by_user_id(char_lookup)

    for char in char_lookup.values():
        if char.corporation_id:
            corporation_ids.add(int(char.corporation_id))

    freight_corps = list(
        EveCorporation.objects.filter(corporation_id=FREIGHT_CORPORATION_ID)
    )
    for corp in freight_corps:
        corporation_ids.add(corp.corporation_id)

    freight_corp = next(iter(freight_corps), None)
    freight_corp_name = (
        freight_corp_display_name()
        if has_freight_corp_acceptor
        else (freight_corp.name if freight_corp and freight_corp.name else "")
    )

    resolved = _resolve_contract_parties(
        contracts,
        char_lookup,
        chars_by_user,
        freight_corp_name,
        corporation_ids,
    )
    corps = _corp_map(corporation_ids)
    alliances = _alliance_map(
        _alliance_ids_for_rows(char_lookup, resolved, corps)
    )

    return [
        _csv_row(
            *party,
            location_short_names=location_short_names,
            location_details=location_details,
            corps=corps,
            alliances=alliances,
            freight_corp=freight_corp,
            freight_corp_name=freight_corp_name,
        )
        for party in resolved
    ]


def render_freight_history_csv(contracts=None) -> str:
    """Return CSV text for finished freight contracts."""
    if contracts is None:
        contracts = list(
            FreightContract.objects.finished().order_by("-date_completed")
        )

    rows = build_freight_history_csv_rows(contracts)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
