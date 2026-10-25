"""Public and admin corporation profile payloads."""

from __future__ import annotations

import re

from django.conf import settings

from alliance.models import AllianceHealthSnapshot
from eveonline.helpers.characters.identity import (
    owner_user_ids,
    primary_characters_for_users,
)
from eveonline.helpers.corporations.discord_bot import (
    BOT_PERMISSIONS,
    page_invite_url,
)
from eveonline.helpers.corporations.stats_cache import corporation_stats
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EveCorporationMedia,
)
from groups.models import UserCommunityStatus

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


def apply_on_leave(rows: list[dict]) -> None:
    """Mark leaders whose community status is On Leave (one query)."""
    user_ids = {row["user_id"] for row in rows if row.get("user_id")}
    on_leave = (
        set(
            UserCommunityStatus.objects.filter(
                user_id__in=user_ids,
                status=UserCommunityStatus.STATUS_ON_LEAVE,
            ).values_list("user_id", flat=True)
        )
        if user_ids
        else set()
    )
    for row in rows:
        row["on_leave"] = row.get("user_id") in on_leave


def public_profile(corporation: EveCorporation) -> dict:
    """Profile payload. Heavy 90-day stats come from the Celery-filled cache
    and are absent (empty/None) until the first refresh finishes."""
    leaders = leadership_rows(corporation)
    stats = corporation_stats(corporation.corporation_id) or {}
    apply_cached_timezones(leaders, stats)
    apply_on_leave(leaders)
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
        "about": _about(corporation, stats),
        "highlights": corporation.highlights or None,
        "activity_summary": corporation.activity_summary or None,
        "media": [_media_item(item) for item in corporation.media.all()],
        "discord_invite_url": page_invite_url(corporation),
    }


def _about(corporation: EveCorporation, stats: dict) -> dict | None:
    about = stats.get("about")
    if about is None:
        if corporation.date_founded is None:
            return None
        return {"founded": corporation.date_founded.isoformat()}
    # ESI's founding date beats the corp-history estimate in the cache.
    if corporation.date_founded:
        about = {**about, "founded": corporation.date_founded.isoformat()}
    return about


def missing_prime_time(corporation: EveCorporation) -> list[dict]:
    leaders = leadership_rows(corporation)
    apply_cached_timezones(
        leaders, corporation_stats(corporation.corporation_id) or {}
    )
    return [
        _public_leader(row) for row in leaders if not row.get("prime_time")
    ]


def corporation_health(corporation_id: int) -> dict:
    """The corp's row from the alliance health snapshot.

    ``active_90d`` is alliance-health activity: any fleet, kill or supply
    signal in 90 days. The member tiers on the same page (summary.fleet_tier)
    count fleets only, so a miner can be active here and inactive there.
    """
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
    configured = settings.DISCORD_BOT_INVITE_URL or ""
    if configured:
        return configured
    client_id = getattr(settings, "DISCORD_CLIENT_ID", "") or ""
    if not client_id:
        return ""
    return (
        "https://discord.com/oauth2/authorize"
        f"?client_id={client_id}&scope=bot&permissions={BOT_PERMISSIONS}"
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
    owners = owner_user_ids(entry[0].character_id for entry in entries)
    primaries = primary_characters_for_users(owners.values())
    seen_users: set[int] = set()
    seen_characters: set[int] = set()
    rows = []
    for character, role in entries:
        user_id = owners.get(character.character_id)
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
        "on_leave": bool(row.get("on_leave")),
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
