"""Helpers to update a character's planetary interaction data from ESI."""

import logging
from datetime import datetime
from decimal import Decimal

import pytz
from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.client import EsiClient, esi_public
from eveonline.models import EveCharacter
from eveonline.models.characters import (
    EveCharacterPlanet,
    EveCharacterPlanetOutput,
)
from eveonline.models.universe import EveUniverseSchematic

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 86400


def _parse_esi_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return (
            timezone.make_aware(value) if timezone.is_naive(value) else value
        )
    # pylint: disable=no-value-for-parameter
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt


# ---------------------------------------------------------------------------
# Supply-chain helpers used by _extract_planet_outputs_with_daily
# ---------------------------------------------------------------------------


def _build_route_indexes(routes):
    """Return (inbound, outbound) maps: pin_id -> [route, ...]."""
    inbound: dict[int, list] = {}
    outbound: dict[int, list] = {}
    for r in routes:
        inbound.setdefault(r["destination_pin_id"], []).append(r)
        outbound.setdefault(r["source_pin_id"], []).append(r)
    return inbound, outbound


def _resolve_extractors(pins, outbound):
    """
    Compute extractor daily outputs and seed node_inflow for their destinations.

    Returns (pin_resolved, node_inflow, harvested).
    pin_resolved[pin_id][type_id]  = daily output of this extractor pin.
    node_inflow[dst_pin][type_id]  = daily units arriving at dst from extractors.
    harvested[type_id]             = total daily harvested across all extractors.
    """
    pin_resolved: dict[int, dict[int, Decimal]] = {}
    node_inflow: dict[int, dict[int, Decimal]] = {}
    harvested: dict[int, Decimal] = {}

    for pin in pins:
        ext = pin.get("extractor_details")
        if not ext:
            continue
        tid = ext.get("product_type_id")
        if not tid:
            continue
        cycle = Decimal(ext.get("cycle_time") or 1)
        qty = Decimal(ext.get("qty_per_cycle") or 0)
        daily = (qty / cycle) * SECONDS_PER_DAY

        pin_resolved[pin["pin_id"]] = {tid: daily}
        harvested[tid] = harvested.get(tid, Decimal(0)) + daily

        # Propagate via each outbound route, capped by that route's configured
        # delivery rate (handles extractors that split output to multiple pins).
        for r in outbound.get(pin["pin_id"], []):
            if r["content_type_id"] != tid:
                continue
            route_daily = min(
                (Decimal(r.get("quantity") or 0) / cycle) * SECONDS_PER_DAY,
                daily,
            )
            dst = r["destination_pin_id"]
            node_inflow.setdefault(dst, {})
            node_inflow[dst][tid] = (
                node_inflow[dst].get(tid, Decimal(0)) + route_daily
            )

    return pin_resolved, node_inflow, harvested


def _outbound_by_type(fpid, outbound):
    """Aggregate outbound route quantities by output type for a factory pin."""
    result: dict[int, Decimal] = {}
    for r in outbound.get(fpid, []):
        tid = r["content_type_id"]
        result[tid] = result.get(tid, Decimal(0)) + Decimal(
            r.get("quantity") or 0
        )
    return result


def _has_pending_upstream(src, in_type, fpid, unresolved, outbound):
    """
    Return True if any OTHER unresolved factory will still push in_type into
    src (meaning node_inflow[src][in_type] may increase in a later pass).
    """
    return any(
        fpid2 != fpid
        and any(
            r["destination_pin_id"] == src and r["content_type_id"] == in_type
            for r in outbound.get(fpid2, [])
        )
        for fpid2 in unresolved
    )


def _inbound_supply_for_factory(  # pylint: disable=too-many-arguments
    fpid,
    in_rs,
    extractor_pin_ids,
    factory_pin_ids,
    unresolved,
    pin_by_id,
    schematic_cycle_seconds,
    node_inflow,
    pin_resolved,
    factory_cycle,
    outbound,
):
    """
    Evaluate available supply vs required rate for each input type of a factory.

    Returns (defer, use_capacity, supply_by_type, required_by_type).
    - defer=True       → retry this factory next pass (upstream not resolved yet).
    - use_capacity=True → fall back to capacity (input from inter-planet import).
    """
    supply_by_type: dict[int, Decimal] = {}
    required_by_type: dict[int, Decimal] = {}

    for in_r in in_rs:
        src = in_r["source_pin_id"]
        in_type = in_r["content_type_id"]
        in_qty = Decimal(in_r.get("quantity") or 0)
        if in_qty == 0:
            continue

        req = (in_qty / factory_cycle) * SECONDS_PER_DAY
        required_by_type[in_type] = (
            required_by_type.get(in_type, Decimal(0)) + req
        )

        if src in extractor_pin_ids:
            ext_details = pin_by_id[src].get("extractor_details", {})
            ext_cycle = Decimal(ext_details.get("cycle_time") or 1)
            ext_daily = pin_resolved.get(src, {}).get(in_type, Decimal(0))
            route_cap = (in_qty / ext_cycle) * SECONDS_PER_DAY
            supply = min(ext_daily, route_cap)

        elif src in factory_pin_ids:
            if src in unresolved:
                return True, False, supply_by_type, required_by_type
            upstream_cycle = Decimal(
                schematic_cycle_seconds.get(pin_by_id[src].get("schematic_id"))
                or 3600
            )
            upstream_daily = pin_resolved.get(src, {}).get(in_type, Decimal(0))
            route_cap = (in_qty / upstream_cycle) * SECONDS_PER_DAY
            supply = min(upstream_daily, route_cap)

        else:
            # Storage or launchpad source.
            if _has_pending_upstream(src, in_type, fpid, unresolved, outbound):
                return True, False, supply_by_type, required_by_type
            supply_val = node_inflow.get(src, {}).get(in_type)
            if supply_val is None:
                # No in-planet source contributed this type → inter-planet import.
                return False, True, supply_by_type, required_by_type
            supply = supply_val

        supply_by_type[in_type] = (
            supply_by_type.get(in_type, Decimal(0)) + supply
        )

    return False, False, supply_by_type, required_by_type


def _apply_supply_cap(capacity_daily, supply_by_type, required_by_type):
    """Apply supply-limiting factor and return actual daily factory output."""
    limiting_factor = Decimal(1)
    for in_type, req in required_by_type.items():
        if req > 0:
            avail = supply_by_type.get(in_type, Decimal(0))
            limiting_factor = min(limiting_factor, avail / req)
    return capacity_daily * min(Decimal(1), limiting_factor)


def _propagate_factory_output(
    fpid,
    out_type,
    daily,
    factory_cycle,
    outbound,
    node_inflow,
    pin_resolved,
    produced,
):
    """Record factory output and push it into node_inflow for downstream pins."""
    produced[out_type] = produced.get(out_type, Decimal(0)) + daily
    pin_resolved[fpid] = {out_type: daily}
    for r in outbound.get(fpid, []):
        if r["content_type_id"] != out_type:
            continue
        route_cap = (
            Decimal(r.get("quantity") or 0) / factory_cycle
        ) * SECONDS_PER_DAY
        route_daily = min(daily, route_cap)
        dst = r["destination_pin_id"]
        node_inflow.setdefault(dst, {})
        node_inflow[dst][out_type] = (
            node_inflow[dst].get(out_type, Decimal(0)) + route_daily
        )


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------


def _extract_planet_outputs_with_daily(planet_detail, schematic_cycle_seconds):
    """
    Analyse a planet's pins and routes; return harvested and produced
    type_id -> daily_quantity (estimated units per day).

    Factory output is supply-limited: each factory's run-rate is capped by the
    daily input supply that flows into it through the route graph (ultimately
    sourced from extractors on the same planet).  The algorithm propagates
    extractor output through storage/launchpad buffers to each factory, then
    resolves factories in topological order so multi-tier chains (P1→P2→P3)
    cascade correctly.

    Fallbacks that use capacity instead of supply limit:
    - Factory has no inbound routes recorded (simplified or old ESI data).
    - Factory's inbound supply traces to a launchpad with no in-planet feed
      (inter-planet imports — we have no way to measure the import rate).
    - Factory cannot be resolved after all passes (circular or missing data).

    schematic_cycle_seconds: dict schematic_id -> cycle_time in seconds
    (from EveUniverseSchematic).
    """
    pins = planet_detail.get("pins", [])
    routes = planet_detail.get("routes", [])
    pin_by_id = {p["pin_id"]: p for p in pins}

    inbound, outbound = _build_route_indexes(routes)
    extractor_pin_ids = {
        p["pin_id"] for p in pins if p.get("extractor_details")
    }
    factory_pin_ids = {p["pin_id"] for p in pins if p.get("schematic_id")}

    pin_resolved, node_inflow, harvested = _resolve_extractors(pins, outbound)

    produced: dict[int, Decimal] = {}
    unresolved = list(factory_pin_ids)
    max_passes = len(factory_pin_ids) + 2
    passes = 0

    while unresolved and passes < max_passes:
        passes += 1
        resolved_now: list[int] = []

        for fpid in unresolved:
            fp = pin_by_id[fpid]
            factory_cycle = Decimal(
                schematic_cycle_seconds.get(fp.get("schematic_id")) or 3600
            )
            out_by_type = _outbound_by_type(fpid, outbound)
            if not out_by_type:
                resolved_now.append(fpid)
                continue

            out_type, out_qty = next(iter(out_by_type.items()))
            capacity_daily = (out_qty / factory_cycle) * SECONDS_PER_DAY

            in_rs = inbound.get(fpid, [])
            if not in_rs:
                # No inbound routes: fall back to capacity.
                daily = capacity_daily
            else:
                defer, use_capacity, supply_by_type, required_by_type = (
                    _inbound_supply_for_factory(
                        fpid,
                        in_rs,
                        extractor_pin_ids,
                        factory_pin_ids,
                        unresolved,
                        pin_by_id,
                        schematic_cycle_seconds,
                        node_inflow,
                        pin_resolved,
                        factory_cycle,
                        outbound,
                    )
                )
                if defer:
                    continue
                daily = (
                    capacity_daily
                    if use_capacity
                    else _apply_supply_cap(
                        capacity_daily, supply_by_type, required_by_type
                    )
                )

            resolved_now.append(fpid)
            _propagate_factory_output(
                fpid,
                out_type,
                daily,
                factory_cycle,
                outbound,
                node_inflow,
                pin_resolved,
                produced,
            )

        if not resolved_now:
            break
        unresolved = [f for f in unresolved if f not in set(resolved_now)]

    # Fallback: any factories still unresolved get capacity-based output.
    for fpid in unresolved:
        fp = pin_by_id[fpid]
        factory_cycle = Decimal(
            schematic_cycle_seconds.get(fp.get("schematic_id")) or 3600
        )
        for ot, oq in _outbound_by_type(fpid, outbound).items():
            produced[ot] = (
                produced.get(ot, Decimal(0))
                + (oq / factory_cycle) * SECONDS_PER_DAY
            )

    return harvested, produced


def _schematic_ids_from_planet_detail(planet_detail):
    """Return set of schematic_ids used by factory pins on this planet."""
    pins = planet_detail.get("pins", [])
    return {p["schematic_id"] for p in pins if p.get("schematic_id")}


def ensure_schematics_cached(schematic_ids):
    """
    Fetch PI schematics from ESI and store in EveUniverseSchematic.

    Public endpoint; safe to call with any list of schematic_ids (e.g. from
    planet pins). Missing or failed IDs are skipped; existing rows are updated.
    """
    if not schematic_ids:
        return
    esi = esi_public()
    for schematic_id in schematic_ids:
        try:
            response = esi.get_universe_schematic(schematic_id)
            if not response.success():
                logger.debug(
                    "Could not fetch schematic %s: %s",
                    schematic_id,
                    response.response_code,
                )
                continue
            data = response.results()
            EveUniverseSchematic.objects.update_or_create(
                schematic_id=schematic_id,
                defaults={
                    "schematic_name": data.get("schematic_name", ""),
                    "cycle_time": data.get("cycle_time", 0),
                },
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "Failed to fetch/store schematic %s: %s",
                schematic_id,
                e,
            )


def update_character_planets(eve_character_id: int) -> int:
    """
    Fetch planetary colonies from ESI and update EveCharacterPlanet /
    EveCharacterPlanetOutput rows.  Returns the number of planets synced.
    """
    character = EveCharacter.objects.filter(
        character_id=eve_character_id
    ).first()
    if not character:
        logger.warning(
            "Character %s not found, skipping planets sync",
            eve_character_id,
        )
        return 0
    if character.esi_suspended:
        logger.debug(
            "Skipping planets for ESI-suspended character %s",
            eve_character_id,
        )
        return 0

    esi = EsiClient(character)
    planets_response = esi.get_character_planets()
    if not planets_response.success():
        logger.warning(
            "Skipping planets for character %s, %s",
            eve_character_id,
            planets_response.response_code,
        )
        return 0

    planets_data = planets_response.results() or []
    active_planet_ids = set()
    seen_schematic_ids = set()

    for planet_entry in planets_data:
        planet_id = planet_entry["planet_id"]
        active_planet_ids.add(planet_id)

        planet_obj, _ = EveCharacterPlanet.objects.update_or_create(
            character=character,
            planet_id=planet_id,
            defaults={
                "planet_type": planet_entry.get("planet_type", ""),
                "solar_system_id": planet_entry.get("solar_system_id", 0),
                "upgrade_level": planet_entry.get("upgrade_level", 0),
                "num_pins": planet_entry.get("num_pins", 0),
                "last_update": _parse_esi_date(
                    planet_entry.get("last_update")
                ),
            },
        )

        detail_response = esi.get_character_planet_details(planet_id)
        if not detail_response.success():
            logger.warning(
                "Could not fetch planet %s detail for character %s (%s)",
                planet_id,
                eve_character_id,
                detail_response.response_code,
            )
            continue

        detail_data = detail_response.results()
        planet_schematic_ids = _schematic_ids_from_planet_detail(detail_data)
        seen_schematic_ids |= planet_schematic_ids
        ensure_schematics_cached(planet_schematic_ids)

        cycle_map = dict(
            EveUniverseSchematic.objects.filter(
                schematic_id__in=planet_schematic_ids
            ).values_list("schematic_id", "cycle_time")
        )
        harvested, produced = _extract_planet_outputs_with_daily(
            detail_data, cycle_map
        )

        _sync_planet_outputs(planet_obj, harvested, produced)

        # Record that we successfully synced this planet (used to exclude stale
        # planets from industry producer lists).
        planet_obj.last_update = timezone.now()
        planet_obj.save(update_fields=["last_update"])

    ensure_schematics_cached(seen_schematic_ids)

    # Remove planets the character no longer has colonies on
    EveCharacterPlanet.objects.filter(character=character).exclude(
        planet_id__in=active_planet_ids
    ).delete()

    logger.info(
        "Synced %s planet(s) for character %s",
        len(planets_data),
        eve_character_id,
    )
    return len(planets_data)


def _sync_planet_outputs(planet_obj, harvested_dict, produced_dict):
    """
    Replace the planet's output rows with the current set.
    harvested_dict and produced_dict are type_id -> daily_quantity.
    """
    desired = set()
    for type_id in harvested_dict:
        desired.add((type_id, EveCharacterPlanetOutput.OutputType.HARVESTED))
    for type_id in produced_dict:
        desired.add((type_id, EveCharacterPlanetOutput.OutputType.PRODUCED))

    existing = {
        (o.eve_type_id, o.output_type): o
        for o in planet_obj.outputs.select_related("eve_type").all()
    }
    to_delete = set(existing.keys()) - desired
    to_create = desired - set(existing.keys())

    if to_delete:
        ids = [existing[key].pk for key in to_delete]
        EveCharacterPlanetOutput.objects.filter(pk__in=ids).delete()

    for type_id, output_type in to_create:
        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
        daily = (
            harvested_dict.get(type_id, Decimal(0))
            if output_type == EveCharacterPlanetOutput.OutputType.HARVESTED
            else produced_dict.get(type_id, Decimal(0))
        )
        EveCharacterPlanetOutput.objects.create(
            planet=planet_obj,
            eve_type=eve_type,
            output_type=output_type,
            daily_quantity=daily,
        )

    for (type_id, output_type), obj in existing.items():
        if (type_id, output_type) in desired:
            daily = (
                harvested_dict.get(type_id, Decimal(0))
                if output_type == EveCharacterPlanetOutput.OutputType.HARVESTED
                else produced_dict.get(type_id, Decimal(0))
            )
            if obj.daily_quantity != daily:
                obj.daily_quantity = daily
                obj.save(update_fields=["daily_quantity"])
