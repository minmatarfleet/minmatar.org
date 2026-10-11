"""Public and admin corporation profile payloads."""

from __future__ import annotations

import re

from django.conf import settings
from esi.models import Token

from alliance.models import AllianceHealthSnapshot
from eveonline.helpers.corporations.stats_cache import corporation_stats
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationMedia,
    EvePlayer,
)

_YOUTUBE_ID = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))([A-Za-z0-9_-]{6,})"
)
_BARE_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{6,}$")


def load_corporation(corporation_id: int) -> EveCorporation | None:
    return (
        EveCorporation.objects.select_related(
            "ceo", "alliance", "faction", "discord_guild"
        )
        .prefetch_related("directors", "recruiters", "stewards", "media")
        .filter(corporation_id=corporation_id)
        .first()
    )


def registered_user_ids(corporation: EveCorporation) -> list[int]:
    return list(
        {
            user_id
            for user_id in EveCharacter.objects.filter(
                corporation_id=corporation.corporation_id,
                user_id__isnull=False,
            ).values_list("user_id", flat=True)
            if user_id
        }
    )


def leadership_rows(corporation: EveCorporation) -> list[dict]:
    """Public roster of mains: one row per person, highest role kept."""
    entries: list[tuple[EveCharacter, str]] = []
    if corporation.ceo_id and corporation.ceo is not None:
        entries.append((corporation.ceo, "ceo"))
    for character in corporation.directors.all():
        entries.append((character, "director"))
    for character in corporation.recruiters.all():
        entries.append((character, "recruiter"))
    for character in corporation.stewards.all():
        entries.append((character, "steward"))
    return _collapse_leadership_to_mains(entries)


def apply_cached_timezones(rows: list[dict], stats: dict) -> None:
    """Fill prime_time / observed_prime_times from cached stats (no queries).

    Rows stay empty until the first refresh has run.
    """
    declared = stats.get("declared_by_user") or {}
    observed = stats.get("observed_by_user") or {}
    for row in rows:
        user_id = row.get("user_id")
        row["prime_time"] = declared.get(user_id) if user_id else None
        row["observed_prime_times"] = (
            observed.get(user_id, []) if user_id else []
        )


def public_profile(corporation: EveCorporation) -> dict:
    """Profile payload. Heavy 90-day stats come from the Celery-filled cache
    and are absent (empty/None) until the first refresh finishes."""
    leaders = leadership_rows(corporation)
    stats = corporation_stats(corporation.corporation_id) or {}
    apply_cached_timezones(leaders, stats)
    return {
        "ticker": corporation.ticker or None,
        "member_count": corporation.member_count,
        "human_count": stats.get("human_count")
        or len(registered_user_ids(corporation)),
        "ceo": _ceo(corporation),
        "leadership": [_public_leader(row) for row in leaders],
        "timezone_distribution": stats.get("timezone_distribution", []),
        "weekday_distribution": stats.get("weekday_distribution", []),
        "public_summary": stats.get("public_summary"),
        "application_process": stats.get("application_process"),
        "highlights": corporation.highlights or None,
        "activity_summary": corporation.activity_summary or None,
        "media": [_media_item(item) for item in corporation.media.all()],
        "discord_invite_url": corporation.discord_invite_url or None,
    }


def missing_prime_time(corporation: EveCorporation) -> list[dict]:
    leaders = leadership_rows(corporation)
    apply_cached_timezones(
        leaders, corporation_stats(corporation.corporation_id) or {}
    )
    return [
        _public_leader(row) for row in leaders if not row.get("prime_time")
    ]


def corporation_health(corporation_id: int) -> dict:
    snapshot = AllianceHealthSnapshot.objects.order_by("-computed_at").first()
    if snapshot is None:
        return {}
    for row in snapshot.payload.get("corporations") or []:
        if row.get("corporation_id") == corporation_id:
            return {
                "humans": row.get("humans"),
                "active_90d": row.get("active_90d"),
                "active_90d_pct": row.get("active_90d_pct"),
                "growth_90d_pct": row.get("growth_90d_pct"),
            }
    return {}


def bot_invite_url() -> str:
    configured = getattr(settings, "DISCORD_BOT_INVITE_URL", "") or ""
    if configured:
        return configured
    client_id = getattr(settings, "DISCORD_CLIENT_ID", "") or ""
    if not client_id:
        return ""
    return (
        "https://discord.com/oauth2/authorize"
        f"?client_id={client_id}&scope=bot&permissions=8"
    )


def discord_status(corporation: EveCorporation) -> dict:
    guild = corporation.discord_guild
    return {
        "discord_bot_present": bool(guild and guild.is_active),
        "discord_guild_name": guild.name if guild else None,
        "discord_invite_url": corporation.discord_invite_url or None,
        "bot_invite_url": bot_invite_url() or None,
    }


def split_timezones(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def split_requirements(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split("\n") if part.strip()]


def _collapse_leadership_to_mains(
    entries: list[tuple[EveCharacter, str]],
) -> list[dict]:
    characters = [entry[0] for entry in entries]
    primaries, token_user_ids = _primary_characters_by_user(characters)
    seen_users: set[int] = set()
    seen_characters: set[int] = set()
    rows = []
    for character, role in entries:
        user_id = _owning_user_id(character, token_user_ids)
        display = primaries.get(user_id) if user_id else None
        if display is None:
            display = character
        if user_id is not None:
            if user_id in seen_users:
                continue
            seen_users.add(user_id)
        if display.character_id in seen_characters:
            continue
        seen_characters.add(display.character_id)
        rows.append(_leader(display, role, user_id=user_id))
    return rows


def _primary_characters_by_user(
    characters: list[EveCharacter],
) -> tuple[dict[int, EveCharacter], dict[int, int]]:
    token_ids = [
        character.token_id
        for character in characters
        if not character.user_id and character.token_id
    ]
    token_user_ids: dict[int, int] = {}
    if token_ids:
        token_user_ids = {
            token_id: user_id
            for token_id, user_id in Token.objects.filter(
                id__in=token_ids
            ).values_list("id", "user_id")
            if user_id
        }
    user_ids = {
        character.user_id for character in characters if character.user_id
    }
    user_ids.update(token_user_ids.values())
    primaries: dict[int, EveCharacter] = {}
    if not user_ids:
        return primaries, token_user_ids
    players = EvePlayer.objects.filter(
        user_id__in=user_ids,
        primary_character__isnull=False,
    ).select_related("primary_character")
    for player in players:
        if player.primary_character is not None:
            primaries[player.user_id] = player.primary_character
    return primaries, token_user_ids


def _owning_user_id(
    character: EveCharacter, token_user_ids: dict[int, int]
) -> int | None:
    if character.user_id:
        return character.user_id
    if character.token_id:
        return token_user_ids.get(character.token_id)
    return None


def _leader(
    character: EveCharacter,
    role: str,
    user_id: int | None = None,
) -> dict:
    if user_id is None:
        user_id = character.user_id
    return {
        "character_id": character.character_id,
        "character_name": character.character_name,
        "role": role,
        "user_id": user_id,
        "prime_time": None,
        "observed_prime_times": [],
    }


def _public_leader(row: dict) -> dict:
    return {
        "character_id": row["character_id"],
        "character_name": row["character_name"],
        "role": row["role"],
        "prime_time": row.get("prime_time"),
        "observed_prime_times": row.get("observed_prime_times") or [],
    }


def _ceo(corporation: EveCorporation) -> dict | None:
    if corporation.ceo is None:
        return None
    return {
        "character_id": corporation.ceo.character_id,
        "character_name": corporation.ceo.character_name,
    }


def _media_item(item: EveCorporationMedia) -> dict:
    return {
        "id": item.id,
        "sort_order": item.sort_order,
        "kind": item.kind,
        "url": item.url or None,
        "post_id": item.post_id,
        "caption": item.caption,
        "youtube_id": (
            youtube_id_from_url(item.url)
            if item.kind == EveCorporationMedia.YOUTUBE
            else None
        ),
    }


def youtube_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = _YOUTUBE_ID.search(url)
    if match:
        return match.group(1)
    if _BARE_YOUTUBE_ID.fullmatch(url):
        return url
    return None
