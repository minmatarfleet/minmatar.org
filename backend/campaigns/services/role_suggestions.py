"""Who on the coordination Discord could be invited, and as which character.

Lists every member of a campaign's own coordination server and guesses the
EVE character behind each one, so the inviter picks a role instead of
typing names. The guess is only a recommendation: nothing is stored until
someone invites that member (``roles.add``).

A member's character comes from, in order:

- ``linked``: their Discord account is linked to someone on the site
  (that person's main character).
- ``site``: their server nickname, display name or username, cleaned of
  tickers and decorations, is exactly a character on the site.
- ``esi``: the same names, looked up in EVE by exact name.

Only a server of the campaign's own: on our alliance server everyone is
already a member, and the list would be thousands long.
"""

from __future__ import annotations

import logging
import re

from django.core.cache import cache
from django.db.models.functions import Lower

from campaigns.models import Campaign, CampaignRoleMember

logger = logging.getLogger(__name__)

# Longer than the 15-minute role sync, which refreshes it (``warm``).
CACHE_SECONDS = 20 * 60
ESI_BATCH = 500

LINKED = "linked"
SITE = "site"
ESI = "esi"

TAG_MATCH = "match"
TAG_MISMATCH = "mismatch"

# "[TICK] Name", "Name [TICK]", "(alt) Name", "Name | Corp", "Name - FC".
_BRACKETS = re.compile(r"[\[\(\{<][^\]\)\}>]*[\]\)\}>]")
_SPLIT = re.compile(r"\s+[|/\-–—]\s+|\s*\|\s*")
# EVE names: letters, digits, spaces, hyphens and apostrophes, 3-37 long.
_EVE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 '\-.]{1,35}[A-Za-z0-9.']$")


def cache_key(campaign: Campaign) -> str:
    return f"campaigns:role-suggestions:{campaign.id}"


def forget(campaign: Campaign) -> None:
    cache.delete(cache_key(campaign))


_TAG = re.compile(r"[\[\(<]\s*([A-Za-z0-9.\-_ ]{2,10})\s*[\]\)>]")


def tag_of(member: dict) -> str:
    """The alliance or corporation ticker a member wears in their name on
    the server ("[FRONT] Aiel Bladesire" -> "FRONT"), upper case."""
    user = member.get("user") or {}
    for value in (member.get("nick"), user.get("global_name")):
        found = _TAG.search(str(value or ""))
        if found:
            return found.group(1).strip().upper()
    return ""


def avatar_url(member: dict) -> str:
    user = member.get("user") or {}
    if not user.get("avatar"):
        return ""
    return (
        f"https://cdn.discordapp.com/avatars/{user['id']}/"
        f"{user['avatar']}.png?size=64"
    )


def candidate_names(member: dict) -> list[str]:
    """The names a member might use for their character, best first.

    The account username only when they set no server nickname or display
    name: usernames are rarely a character's name ("u12" is one in EVE).
    """
    user = member.get("user") or {}
    raw = [member.get("nick"), user.get("global_name")]
    out = _names_from(raw)
    return out or _names_from([user.get("username")])


def _names_from(raw: list) -> list[str]:
    out: list[str] = []
    for value in raw:
        if not value:
            continue
        cleaned = _BRACKETS.sub(" ", str(value))
        for part in [cleaned, *_SPLIT.split(cleaned)]:
            name = " ".join(part.split())
            if (
                name
                and _EVE_NAME.match(name)
                and name.lower() not in {existing.lower() for existing in out}
            ):
                out.append(name)
    return out


def _display_name(member: dict) -> str:
    user = member.get("user") or {}
    return (
        member.get("nick")
        or user.get("global_name")
        or user.get("username")
        or ""
    )


def _linked(discord_ids: set[int]) -> dict[int, tuple[int, str]]:
    """Discord id -> (character id, name) of the linked site user's main."""
    # pylint: disable=import-outside-toplevel
    from discord.models import DiscordUser
    from eveonline.models import EvePlayer

    users = dict(
        DiscordUser.objects.filter(id__in=discord_ids).values_list(
            "user_id", "id"
        )
    )
    out = {}
    for player in EvePlayer.objects.filter(
        user_id__in=list(users), primary_character__isnull=False
    ).select_related("primary_character"):
        character = player.primary_character
        out[users[player.user_id]] = (
            character.character_id,
            character.character_name,
        )
    return out


def _on_site(names: set[str]) -> dict[str, tuple[int, str]]:
    """Lower-case name -> (character id, exact name) for site characters."""
    # pylint: disable-next=import-outside-toplevel
    from eveonline.models import EveCharacter

    if not names:
        return {}
    rows = (
        EveCharacter.objects.annotate(lower_name=Lower("character_name"))
        .filter(lower_name__in=[name.lower() for name in names])
        .values_list("lower_name", "character_id", "character_name")
    )
    return {lower: (cid, name) for lower, cid, name in rows}


def _in_eve(names: set[str]) -> dict[str, tuple[int, str]]:
    """Lower-case name -> (character id, exact name) from ESI's exact-name
    lookup. Empty when ESI does not answer."""
    # pylint: disable-next=import-outside-toplevel
    from eveonline.client import EsiClient

    found: dict[str, tuple[int, str]] = {}
    ordered = sorted(names)
    for start in range(0, len(ordered), ESI_BATCH):
        batch = ordered[start : start + ESI_BATCH]
        response = EsiClient(None).resolve_universe_ids(batch)
        if not response.success():
            logger.info("ESI name lookup failed for role suggestions")
            continue
        data = response.data if isinstance(response.data, dict) else {}
        for row in data.get("characters") or []:
            name = row.get("name") or ""
            found[name.lower()] = (int(row["id"]), name)
    return found


def _tickers(corp_ids: set[int], alliance_ids: set[int]) -> dict[int, str]:
    """Entity id -> ticker, from the site, else ESI (one call each)."""
    # pylint: disable=import-outside-toplevel
    from eveonline.client import EsiClient
    from eveonline.models import EveAlliance, EveCorporation

    found = {
        entity: ticker
        for entity, ticker in EveCorporation.objects.filter(
            corporation_id__in=corp_ids
        ).values_list("corporation_id", "ticker")
        if ticker
    }
    found.update(
        (entity, ticker)
        for entity, ticker in EveAlliance.objects.filter(
            alliance_id__in=alliance_ids
        ).values_list("alliance_id", "ticker")
        if ticker
    )
    client = EsiClient(None)
    for entity in sorted(alliance_ids - set(found)):
        response = client.get_alliance(entity)
        if response.success() and isinstance(response.data, dict):
            found[entity] = response.data.get("ticker") or ""
    for entity in sorted(corp_ids - set(found)):
        response = client.get_corporation(entity)
        if response.success() and isinstance(response.data, dict):
            found[entity] = response.data.get("ticker") or ""
    return found


def _affiliations(character_ids: list[int]) -> dict[int, dict]:
    """Character id -> corporation and alliance ids and names."""
    # pylint: disable=import-outside-toplevel
    from eveonline.client import EsiClient
    from eveonline.models import EveAlliance, EveCharacter, EveCorporation

    if not character_ids:
        return {}
    ids: dict[int, tuple[int | None, int | None]] = {
        cid: (corp, alliance)
        for cid, corp, alliance in EveCharacter.objects.filter(
            character_id__in=character_ids
        ).values_list("character_id", "corporation_id", "alliance_id")
    }
    unknown = [cid for cid in character_ids if cid not in ids]
    for start in range(0, len(unknown), 1000):
        response = EsiClient(None).get_character_affiliations(
            unknown[start : start + 1000]
        )
        if response.success():
            for row in response.results() or []:
                ids[int(row["character_id"])] = (
                    row.get("corporation_id"),
                    row.get("alliance_id"),
                )
    corp_ids = {corp for corp, _ in ids.values() if corp}
    alliance_ids = {alliance for _, alliance in ids.values() if alliance}
    names = dict(
        EveCorporation.objects.filter(corporation_id__in=corp_ids).values_list(
            "corporation_id", "name"
        )
    )
    names.update(
        EveAlliance.objects.filter(alliance_id__in=alliance_ids).values_list(
            "alliance_id", "name"
        )
    )
    missing = [
        entity for entity in corp_ids | alliance_ids if entity not in names
    ]
    for start in range(0, len(missing), 1000):
        response = EsiClient(None).resolve_universe_names(
            missing[start : start + 1000]
        )
        if response.success():
            for row in response.results() or []:
                names[int(row["id"])] = row.get("name", "")
    return {
        cid: {
            "corporation_id": corp,
            "alliance_id": alliance,
            "corporation_name": names.get(corp, "") or "",
            "alliance_name": names.get(alliance, "") or "",
        }
        for cid, (corp, alliance) in ids.items()
    }


def match_members(members: list[dict]) -> list[dict]:
    by_id = {int(m["user"]["id"]): m for m in members}
    linked = _linked(set(by_id))
    names = {
        discord_id: candidate_names(member)
        for discord_id, member in by_id.items()
        if discord_id not in linked
    }
    every_name = {name for found in names.values() for name in found}
    site = _on_site(every_name)
    left = {
        name
        for found in names.values()
        if not any(name.lower() in site for name in found)
        for name in found
    }
    eve = _in_eve(left) if left else {}

    rows = []
    for discord_id, member in by_id.items():
        character, match = linked.get(discord_id), LINKED
        if character is None:
            match = ""
            for name in names.get(discord_id, []):
                if name.lower() in site:
                    character, match = site[name.lower()], SITE
                    break
            else:
                for name in names.get(discord_id, []):
                    if name.lower() in eve:
                        character, match = eve[name.lower()], ESI
                        break
        rows.append(
            {
                "discord_user_id": discord_id,
                "discord_name": _display_name(member),
                "character_id": character[0] if character else None,
                "character_name": character[1] if character else "",
                "match": match,
                "tag": tag_of(member),
                "avatar_url": avatar_url(member),
            }
        )
    affiliation = _affiliations(
        [row["character_id"] for row in rows if row["character_id"]]
    )
    for row in rows:
        found = affiliation.get(row["character_id"], {})
        row["corporation_name"] = found.get("corporation_name", "")
        row["alliance_name"] = found.get("alliance_name", "")
    _check_tags(rows, affiliation)
    return rows


def _check_tags(rows: list[dict], affiliation: dict[int, dict]) -> None:
    """Set each row's ``tag_check``. Looks up only the tickers it needs:
    the alliance's first, the corporation's only when that is no match,
    so a big server costs few ESI calls."""
    tagged = [row for row in rows if row["tag"] and row["character_id"]]
    of = {
        row["character_id"]: affiliation.get(row["character_id"], {})
        for row in tagged
    }
    alliance_tickers = _tickers(
        set(),
        {
            found["alliance_id"]
            for found in of.values()
            if found.get("alliance_id")
        },
    )
    unsure = [
        row
        for row in tagged
        if alliance_tickers.get(
            of[row["character_id"]].get("alliance_id"), ""
        ).upper()
        != row["tag"]
    ]
    corp_tickers = _tickers(
        {
            of[row["character_id"]]["corporation_id"]
            for row in unsure
            if of[row["character_id"]].get("corporation_id")
        },
        set(),
    )
    for row in rows:
        found = of.get(row["character_id"], {})
        tickers = {
            ticker.upper()
            for ticker in (
                alliance_tickers.get(found.get("alliance_id"), ""),
                corp_tickers.get(found.get("corporation_id"), ""),
            )
            if ticker
        }
        row["tag_check"] = _tag_check(row, tickers)


def _tag_check(row: dict, tickers: set[str]) -> str:
    """Whether the guessed character wears the tag the member does:
    ``match``, ``mismatch`` (a name twin, most likely), or empty when there
    is no tag, no guess, or no ticker known to check against."""
    if not row["tag"] or not row["character_id"] or not tickers:
        return ""
    return TAG_MATCH if row["tag"] in tickers else TAG_MISMATCH


def trusted(row: dict) -> bool:
    """A guess good enough to invite without naming the character."""
    return bool(row["character_id"]) and (
        row["match"] == LINKED or row.get("tag_check") != TAG_MISMATCH
    )


def server_members(campaign: Campaign) -> list[dict] | None:
    """Every human on the campaign's own coordination server, each with a
    guessed character. None when the campaign has no server of its own or
    Discord would not list it. Cached; the role sync refreshes it."""
    if not campaign.coordination_guild_id:
        return None
    cached = cache.get(cache_key(campaign))
    if cached is not None:
        return cached
    # pylint: disable-next=import-outside-toplevel
    from discord.client import DiscordClient

    try:
        listed = DiscordClient(
            guild_id=campaign.coordination_guild_id
        ).get_members()
    except Exception:  # pylint: disable=broad-except
        logger.warning("Campaign %s: could not list members", campaign.id)
        return None
    humans = [
        member
        for member in listed
        if member.get("user") and not member["user"].get("bot")
    ]
    rows = match_members(humans)
    # By tag (untagged last), then sure guesses first, then name.
    rows.sort(
        key=lambda row: (
            not row["tag"],
            row["tag"],
            not trusted(row),
            (row["character_name"] or row["discord_name"]).lower(),
        )
    )
    cache.set(cache_key(campaign), rows, CACHE_SECONDS)
    return rows


def warm(campaign: Campaign) -> None:
    """Rebuild the cached list, from the role sync task, so the Settings
    page reads it instead of asking Discord and ESI in a request."""
    forget(campaign)
    try:
        server_members(campaign)
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Campaign %s: could not list role suggestions", campaign.id
        )


def find(campaign: Campaign, discord_user_id: int) -> dict | None:
    """The suggestion row for one server member, if they are on it."""
    for row in server_members(campaign) or []:
        if row["discord_user_id"] == discord_user_id:
            return row
    return None


def suggestions(campaign: Campaign) -> dict:
    """The API payload: server members with their guessed character and the
    roles they already hold here."""
    rows = server_members(campaign)
    if rows is None:
        return {
            "available": False,
            "own_server": bool(campaign.coordination_guild_id),
            "members": [],
        }
    held: dict[int, set[str]] = {}
    by_character: dict[int, set[str]] = {}
    for discord_id, character_id, kind in CampaignRoleMember.objects.filter(
        role__campaign=campaign
    ).values_list("discord_user_id", "character_id", "role__kind"):
        if discord_id:
            held.setdefault(discord_id, set()).add(kind)
        if character_id:
            by_character.setdefault(character_id, set()).add(kind)
    return {
        "available": True,
        "own_server": True,
        "members": [
            {
                **row,
                "discord_user_id": str(row["discord_user_id"]),
                "roles": sorted(
                    held.get(row["discord_user_id"], set())
                    | by_character.get(row["character_id"] or 0, set())
                ),
            }
            for row in rows
        ],
    }
