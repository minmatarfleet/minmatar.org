"""Name search for the manage screens' entity pickers.

One endpoint, one result shape (id, name, detail, icon_url), so the site's
EntityPicker works for every kind. Kinds with an existing search reuse it:
corporations and alliances go through the campaign entity search (local
rows, then ESI), types through the settings editors' type search.
"""

from __future__ import annotations

from django.db.models import Case, IntegerField, Q, Value, When

from campaigns.services.entities import search_entities
from discord.models import DiscordChannel
from eveonline.models import EveCharacter, EveCorporation, EveLocation
from eveuniverse.models import EveSolarSystem, EveType
from market.helpers.type_search import search_types

MIN_QUERY = 2
LIMIT = 15
SHIP_CATEGORY_ID = 6
IMAGE_SERVER = "https://images.evetech.net"

# Kinds anyone signed in may search: public EVE names and alliance places.
PUBLIC_KINDS = (
    "system",
    "corporation",
    "alliance",
    "type",
    "ship",
    "location",
)
# Kinds that name the alliance's people and Discord: manage screens only.
MANAGER_KINDS = ("character", "discord_channel")
KINDS = PUBLIC_KINDS + MANAGER_KINDS


def _match(entity_id, name, detail="", icon_url=None) -> dict:
    # A string: Discord snowflakes are past JavaScript's safe integers.
    return {
        "id": str(entity_id),
        "name": name,
        "detail": detail or "",
        "icon_url": icon_url,
    }


def _prefix_first(field: str, needle: str):
    """Order key: names starting with the query before names containing it."""
    return Case(
        When(**{f"{field}__istartswith": needle}, then=Value(0)),
        default=Value(1),
        output_field=IntegerField(),
    )


def _systems(needle: str) -> list[dict]:
    rows = (
        EveSolarSystem.objects.filter(name__icontains=needle)
        .select_related("eve_constellation__eve_region")
        .annotate(rank=_prefix_first("name", needle))
        .order_by("rank", "name")[:LIMIT]
    )
    return [
        _match(
            row.id,
            row.name,
            _system_detail(row),
        )
        for row in rows
    ]


def _system_detail(system) -> str:
    region = getattr(
        getattr(system, "eve_constellation", None), "eve_region", None
    )
    security = (
        f"{system.security_status:.1f}"
        if system.security_status is not None
        else ""
    )
    return " · ".join(
        part for part in (security, region.name if region else "") if part
    )


def _entities(user, kind: str, needle: str) -> list[dict]:
    logo = "corporations" if kind == "corporation" else "alliances"
    return [
        _match(
            row["id"],
            row["name"],
            row.get("ticker", ""),
            f"{IMAGE_SERVER}/{logo}/{row['id']}/logo?size=64",
        )
        for row in search_entities(user, kind, needle)
    ]


def _type_icon(type_id: int) -> str:
    return f"{IMAGE_SERVER}/types/{type_id}/icon?size=64"


def _types(needle: str) -> list[dict]:
    return [
        _match(row.id, row.name, "", _type_icon(row.id))
        for row in search_types(needle, LIMIT)
    ]


def _ships(needle: str) -> list[dict]:
    rows = (
        EveType.objects.filter(
            name__icontains=needle,
            published=True,
            eve_group__eve_category_id=SHIP_CATEGORY_ID,
        )
        .select_related("eve_group")
        .annotate(rank=_prefix_first("name", needle))
        .order_by("rank", "name")[:LIMIT]
    )
    return [
        _match(
            row.id,
            row.name,
            row.eve_group.name if row.eve_group else "",
            _type_icon(row.id),
        )
        for row in rows
    ]


def _locations(needle: str) -> list[dict]:
    rows = (
        EveLocation.objects.filter(
            Q(location_name__icontains=needle)
            | Q(short_name__icontains=needle)
            | Q(solar_system_name__icontains=needle)
        )
        .annotate(rank=_prefix_first("location_name", needle))
        .order_by("rank", "location_name")[:LIMIT]
    )
    return [
        _match(row.location_id, row.location_name, row.solar_system_name)
        for row in rows
    ]


def _characters(needle: str) -> list[dict]:
    """Registered characters (they belong to a site user)."""
    rows = list(
        EveCharacter.objects.filter(
            character_name__icontains=needle, user__isnull=False
        )
        .annotate(rank=_prefix_first("character_name", needle))
        .order_by("rank", "character_name")
        .values_list("character_id", "character_name", "corporation_id")[
            :LIMIT
        ]
    )
    corporations = dict(
        EveCorporation.objects.filter(
            corporation_id__in={row[2] for row in rows if row[2]}
        ).values_list("corporation_id", "name")
    )
    return [
        _match(
            character_id,
            name,
            corporations.get(corporation_id, ""),
            f"{IMAGE_SERVER}/characters/{character_id}/portrait?size=64",
        )
        for character_id, name, corporation_id in rows
    ]


def _discord_channels(needle: str) -> list[dict]:
    rows = (
        DiscordChannel.objects.filter(name__icontains=needle)
        .exclude(channel_type=DiscordChannel.CATEGORY)
        .select_related("guild")
        .annotate(rank=_prefix_first("name", needle))
        .order_by("rank", "name")[:LIMIT]
    )
    labels = dict(DiscordChannel.CHANNEL_TYPE_CHOICES)
    return [
        _match(
            row.channel_id,
            f"#{row.name}",
            " · ".join(
                part
                for part in (labels.get(row.channel_type, ""), row.guild.name)
                if part
            ),
        )
        for row in rows
    ]


def search(user, kind: str, query: str) -> list[dict]:
    needle = (query or "").strip()
    if len(needle) < MIN_QUERY:
        return []
    if kind == "system":
        return _systems(needle)
    if kind in ("corporation", "alliance"):
        return _entities(user, kind, needle)
    if kind == "type":
        return _types(needle)
    if kind == "ship":
        return _ships(needle)
    if kind == "location":
        return _locations(needle)
    if kind == "character":
        return _characters(needle)
    if kind == "discord_channel":
        return _discord_channels(needle)
    return []
