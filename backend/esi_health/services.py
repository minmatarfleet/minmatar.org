"""What ESI is broken, for whom, and who can fix it.

One definition of "needs re-adding" for tasks, the account page, the
corporation roster and Manage › ESI health:

- the character belongs to an account and isn't exempt, and
- its token stopped refreshing (esi_suspended), or its token is gone while
  the character once had one (a token level is on record). Tokens deleted
  outside the refresh path left 15 alliance characters in that state with no
  task and an ACTIVE label on the account page.

A character whose token works but lacks a scope it should hold today is
"outdated": a scope added to one of its groups (Basic, Industry, ...) after
it logged in, or a whole group that became required later
(REQUIRED_SCOPE_GROUPS). The scope lists in eveonline.scopes are the source
of truth, so a scope added there asks everyone without a ScopeRollout row.
A ScopeRollout set to "Don't ask" leaves that one scope out, and gives the
scope its label. Director scopes are a corporation's job (corp_director_token).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Optional

from django.db.models import Q
from django.utils import timezone
from esi.models import Token

from discord.models import DiscordUser
from eveonline.helpers.alliances import alliance_corporations
from eveonline.models import EveCharacter, EveCorporation, EvePlayer
from eveonline.helpers.characters import character_configured_scope_groups
from eveonline.scopes import (
    DIRECTOR_SCOPES,
    REQUIRED_SCOPE_GROUPS,
    TokenType,
    scopes_for,
)
from esi_health.models import EsiMessage, ScopeRollout
from groups.models import UserCommunityStatus

MEMBERSHIP_SCOPE = "esi-corporations.read_corporation_membership.v1"
# A pilot gets at most one message from superusers in this window.
MESSAGE_COOLDOWN = timedelta(days=7)

DIRECTOR_OK = "ok"
DIRECTOR_UPDATE = "update"
DIRECTOR_MISSING = "missing"


def lost_token_q(prefix: str = "") -> Q:
    return (
        Q(**{f"{prefix}token__isnull": True})
        & Q(**{f"{prefix}esi_token_level__isnull": False})
        & ~Q(**{f"{prefix}esi_token_level": ""})
    )


def needs_readd_q(prefix: str = "") -> Q:
    """Characters whose owner has to log in again (see module docstring)."""
    return Q(**{f"{prefix}user__isnull": False, f"{prefix}exempt": False}) & (
        Q(**{f"{prefix}esi_suspended": True}) | lost_token_q(prefix)
    )


def needs_readd(character: EveCharacter) -> bool:
    if character.user_id is None or character.exempt:
        return False
    if character.esi_suspended:
        return True
    return character.token_id is None and bool(character.esi_token_level)


def token_scopes(token_ids: Iterable[int]) -> dict[int, set[str]]:
    scopes: dict[int, set[str]] = defaultdict(set)
    ids = [token_id for token_id in token_ids if token_id]
    for token_id, name in Token.scopes.through.objects.filter(
        token_id__in=ids
    ).values_list("token_id", "scope__name"):
        scopes[token_id].add(name)
    return scopes


# --- Scope changes ------------------------------------------------------


def character_groups(character: EveCharacter) -> set[str]:
    groups = set(character.esi_scope_groups or [])
    if character.esi_token_level:
        groups.add(character.esi_token_level)
    return groups


def rollout_applies(rollout: ScopeRollout, groups: set[str]) -> bool:
    """Basic underlies every token type except Public."""
    if rollout.scope_group == TokenType.BASIC.value:
        return bool(groups - {TokenType.PUBLIC.value})
    return rollout.scope_group in groups


# Groups a pilot's own token is checked against. Director scopes are checked
# per corporation, and Executor is the mail sender's token, not a pilot's.
_NOT_PILOT_GROUPS = {
    TokenType.PUBLIC.value,
    TokenType.DIRECTOR.value,
    TokenType.EXECUTOR.value,
}
_KNOWN_GROUPS = {token_type.value for token_type in TokenType}
_GROUP_LABELS = {
    TokenType.FACTION_WARFARE.value: "Faction Warfare",
    TokenType.FLEET_COMMANDER.value: "Fleet Commander",
}


def group_label(group: str) -> str:
    return _GROUP_LABELS.get(group, group)


def expected_groups(character: EveCharacter) -> list[str]:
    """The groups this character's token should hold in full, Basic first.

    Its own groups plus the required ones. Public-only (guest) characters
    hold nothing more.
    """
    own = [
        TokenType.FACTION_WARFARE.value if g == TokenType.CAMPAIGN.value else g
        for g in character_configured_scope_groups(character)
    ]
    if not set(own) - {TokenType.PUBLIC.value}:
        return []
    groups = [TokenType.BASIC.value]
    for group in [*own, *(g.value for g in REQUIRED_SCOPE_GROUPS)]:
        if (
            group in _KNOWN_GROUPS
            and group not in groups
            and group not in _NOT_PILOT_GROUPS
        ):
            groups.append(group)
    return groups


def missing_scope_labels(
    character: EveCharacter,
    scopes: set[str],
    rollouts: list[ScopeRollout],
) -> list[str]:
    """What a new login would add to this working token, as the task says it.

    A required group the character never had reads as the group ("Faction
    Warfare"); scopes added to a group it has read as their ScopeRollout
    label, or "newer <group> scopes" when nobody labelled them. Empty when
    the token is up to date, broken (that's a re-add) or a guest login.
    """
    if character.token_id is None or character.esi_suspended:
        return []
    groups = expected_groups(character)
    if not groups:
        return []
    own = set(character_configured_scope_groups(character))
    if TokenType.CAMPAIGN.value in own:
        own.add(TokenType.FACTION_WARFARE.value)
    labels = {r.scope: r.label for r in rollouts if r.label}
    not_asked = {
        r.scope
        for r in rollouts
        if r.mode == ScopeRollout.MODE_NONE
        and r.scope_group != TokenType.DIRECTOR.value
    }
    covered: set[str] = set()
    result: list[str] = []
    for group in groups:
        wanted = set(scopes_for(TokenType(group))) - not_asked - covered
        missing = wanted - scopes
        covered |= wanted
        if not missing:
            continue
        if group not in own and group != TokenType.BASIC.value:
            found = [group_label(group)]
        else:
            found = [
                labels.get(scope) or f"newer {group_label(group)} scopes"
                for scope in sorted(missing)
            ]
        for label in found:
            if label not in result:
                result.append(label)
    return result


def required_director_scopes(rollouts: Optional[list] = None) -> set[str]:
    """Director scopes, less the ones added later that nobody asks for."""
    rollouts = (
        rollouts if rollouts is not None else list(ScopeRollout.objects.all())
    )
    optional = {
        rollout.scope
        for rollout in rollouts
        if rollout.scope_group == TokenType.DIRECTOR.value
        and rollout.mode != ScopeRollout.MODE_REQUIRE
    }
    return set(DIRECTOR_SCOPES) - optional


# --- Director tokens ----------------------------------------------------


@dataclass
class DirectorHolder:
    character_id: int
    character_name: str
    user_id: Optional[int]
    missing: int


@dataclass
class DirectorStatus:
    state: str
    holders: list[DirectorHolder] = field(default_factory=list)
    # The scopes the best token lacks.
    missing_scopes: list[str] = field(default_factory=list)


def director_statuses(
    corporation_ids: Iterable[int], rollouts: Optional[list] = None
) -> dict[int, DirectorStatus]:
    required = required_director_scopes(rollouts)
    rows = list(
        EveCharacter.objects.filter(
            corporation_id__in=list(corporation_ids),
            token__isnull=False,
            esi_suspended=False,
        ).values(
            "corporation_id",
            "character_id",
            "character_name",
            "user_id",
            "token_id",
        )
    )
    scopes = token_scopes(row["token_id"] for row in rows)
    holders: dict[int, list[tuple[DirectorHolder, set[str]]]] = defaultdict(
        list
    )
    for row in rows:
        granted = scopes.get(row["token_id"], set())
        if MEMBERSHIP_SCOPE not in granted:
            continue
        lacking = required - granted
        holders[row["corporation_id"]].append(
            (
                DirectorHolder(
                    character_id=row["character_id"],
                    character_name=row["character_name"],
                    user_id=row["user_id"],
                    missing=len(lacking),
                ),
                lacking,
            )
        )
    statuses = {}
    for corporation_id in corporation_ids:
        found = sorted(
            holders.get(corporation_id, []),
            key=lambda pair: (pair[0].missing, pair[0].character_name),
        )
        if not found:
            statuses[corporation_id] = DirectorStatus(DIRECTOR_MISSING)
            continue
        best, lacking = found[0]
        statuses[corporation_id] = DirectorStatus(
            DIRECTOR_OK if best.missing == 0 else DIRECTOR_UPDATE,
            holders=[holder for holder, _ in found],
            missing_scopes=sorted(lacking),
        )
    return statuses


# --- Reports for Manage › ESI health -------------------------------------


def _statuses(user_ids: Iterable[int]) -> dict[int, str]:
    return dict(
        UserCommunityStatus.objects.filter(
            user_id__in=list(user_ids)
        ).values_list("user_id", "status")
    )


def _on_leave(status: Optional[str]) -> bool:
    # Alumni are treated as On Leave here: never messaged, tasks paused.
    return status in UserCommunityStatus.AWAY_STATUSES


def last_messages(user_ids: Iterable[int]) -> dict[int, datetime]:
    last: dict[int, datetime] = {}
    for user_id, sent_at in EsiMessage.objects.filter(
        user_id__in=list(user_ids)
    ).values_list("user_id", "sent_at"):
        if user_id not in last or sent_at > last[user_id]:
            last[user_id] = sent_at
    return last


@dataclass
class CorporationHealth:
    corporation_id: int
    name: str
    ticker: str
    members: int
    needs_readd: int
    pilots_active: int
    pilots_on_leave: int
    # The pilots a message would go to: not On Leave.
    active_user_ids: list[int]
    unlinked: int
    director: DirectorStatus
    last_messaged: Optional[datetime]


def corporations_report() -> list[CorporationHealth]:
    corporations = list(
        alliance_corporations().values(
            "corporation_id", "name", "ticker", "member_count"
        )
    )
    ids = [row["corporation_id"] for row in corporations]
    broken = list(
        EveCharacter.objects.filter(corporation_id__in=ids)
        .filter(needs_readd_q())
        .values_list("corporation_id", "user_id")
    )
    unlinked = defaultdict(int)
    for corporation_id in EveCharacter.objects.filter(
        corporation_id__in=ids, user__isnull=True, token__isnull=True
    ).values_list("corporation_id", flat=True):
        unlinked[corporation_id] += 1
    statuses = _statuses({user_id for _, user_id in broken})
    last = last_messages({user_id for _, user_id in broken})
    directors = director_statuses(ids)
    counts = defaultdict(int)
    users = defaultdict(set)
    for corporation_id, user_id in broken:
        counts[corporation_id] += 1
        users[corporation_id].add(user_id)
    report = []
    for row in corporations:
        corporation_id = row["corporation_id"]
        pilots = users.get(corporation_id, set())
        on_leave = {u for u in pilots if _on_leave(statuses.get(u))}
        messaged = [last[u] for u in pilots if u in last]
        report.append(
            CorporationHealth(
                corporation_id=corporation_id,
                name=row["name"],
                ticker=row["ticker"] or "",
                members=row["member_count"] or 0,
                needs_readd=counts.get(corporation_id, 0),
                pilots_active=len(pilots - on_leave),
                pilots_on_leave=len(on_leave),
                active_user_ids=sorted(pilots - on_leave),
                unlinked=unlinked.get(corporation_id, 0),
                director=directors[corporation_id],
                last_messaged=max(messaged) if messaged else None,
            )
        )
    order = {DIRECTOR_MISSING: 0, DIRECTOR_UPDATE: 0, DIRECTOR_OK: 1}
    report.sort(
        key=lambda c: (
            -c.needs_readd,
            order[c.director.state],
            -c.unlinked,
            c.name.lower(),
        )
    )
    return report


@dataclass
class PilotHealth:
    user_id: int
    username: str
    main_character_id: Optional[int]
    main_character_name: str
    corporation_ticker: str
    characters: list[str]
    main_needs_readd: bool
    scope_groups: list[str]
    status: str
    on_leave: bool
    discord_linked: bool
    task_opened_at: Optional[datetime]
    last_messaged: Optional[datetime]


def broken_characters_by_user(
    user_ids: Optional[Iterable[int]] = None,
) -> dict[int, list[EveCharacter]]:
    """Every character to re-add, for owners of one in our corporations."""
    if user_ids is None:
        user_ids = set(
            EveCharacter.objects.filter(
                corporation_id__in=alliance_corporations().values(
                    "corporation_id"
                )
            )
            .filter(needs_readd_q())
            .values_list("user_id", flat=True)
        )
    rows = (
        EveCharacter.objects.filter(user_id__in=list(user_ids))
        .filter(needs_readd_q())
        .only(
            "character_id",
            "character_name",
            "user_id",
            "esi_scope_groups",
            "esi_token_level",
        )
        .order_by("character_name")
    )
    by_user: dict[int, list[EveCharacter]] = defaultdict(list)
    for character in rows:
        by_user[character.user_id].append(character)
    return by_user


def pilots_report() -> list[PilotHealth]:
    # pylint: disable=import-outside-toplevel
    from taskboard.models import Task

    by_user = broken_characters_by_user()
    user_ids = list(by_user)
    players = {
        player.user_id: player
        for player in EvePlayer.objects.filter(
            user_id__in=user_ids
        ).select_related("primary_character", "user")
    }
    tickers = dict(
        EveCorporation.objects.values_list("corporation_id", "ticker")
    )
    statuses = _statuses(user_ids)
    last = last_messages(user_ids)
    discord = set(
        DiscordUser.objects.filter(user_id__in=user_ids).values_list(
            "user_id", flat=True
        )
    )
    tasks = {}
    for user_id, opened in Task.objects.filter(
        rule="reauth_character", status=Task.STATUS_OPEN, user_id__in=user_ids
    ).values_list("user_id", "opened_at"):
        if user_id not in tasks or opened < tasks[user_id]:
            tasks[user_id] = opened
    report = []
    for user_id, characters in by_user.items():
        player = players.get(user_id)
        main = player.primary_character if player else None
        main_broken = bool(
            main
            and any(c.character_id == main.character_id for c in characters)
        )
        names = [c.character_name for c in characters]
        if main_broken:
            names.remove(main.character_name)
            names.insert(0, main.character_name)
        groups = sorted({g for c in characters for g in character_groups(c)})
        status = statuses.get(user_id) or ""
        report.append(
            PilotHealth(
                user_id=user_id,
                username=player.user.username if player else "",
                main_character_id=main.character_id if main else None,
                main_character_name=main.character_name if main else names[0],
                corporation_ticker=(
                    tickers.get(main.corporation_id) or "" if main else ""
                ),
                characters=names,
                main_needs_readd=main_broken,
                scope_groups=groups,
                status=status,
                on_leave=_on_leave(status),
                discord_linked=user_id in discord,
                task_opened_at=tasks.get(user_id),
                last_messaged=last.get(user_id),
            )
        )
    report.sort(
        key=lambda p: (
            p.on_leave,
            not p.main_needs_readd,
            -len(p.characters),
            p.main_character_name.lower(),
        )
    )
    return report


@dataclass
class ScopeProgress:
    rollout: ScopeRollout
    updated: int
    total: int
    # "characters" or "corporations".
    unit: str


def scopes_report() -> list[ScopeProgress]:
    rollouts = list(ScopeRollout.objects.all())
    corporations = list(
        alliance_corporations().values_list("corporation_id", flat=True)
    )
    characters = list(
        EveCharacter.objects.filter(
            corporation_id__in=corporations,
            token__isnull=False,
            esi_suspended=False,
        ).only("token_id", "esi_scope_groups", "esi_token_level")
    )
    scopes = token_scopes(c.token_id for c in characters)
    report = []
    for rollout in rollouts:
        if rollout.scope_group == TokenType.DIRECTOR.value:
            # A corporation is updated when one director token has it.
            statuses = director_statuses(
                corporations,
                rollouts=[
                    (
                        r
                        if r.pk != rollout.pk
                        else ScopeRollout(
                            scope=r.scope,
                            scope_group=r.scope_group,
                            mode=ScopeRollout.MODE_REQUIRE,
                        )
                    )
                    for r in rollouts
                ],
            )
            updated = sum(
                1
                for status in statuses.values()
                if status.holders
                and rollout.scope not in status.missing_scopes
            )
            report.append(
                ScopeProgress(
                    rollout, updated, len(corporations), "corporations"
                )
            )
            continue
        applies = [
            c
            for c in characters
            if rollout_applies(rollout, character_groups(c))
        ]
        updated = sum(
            1
            for c in applies
            if rollout.scope in scopes.get(c.token_id, set())
        )
        report.append(
            ScopeProgress(rollout, updated, len(applies), "characters")
        )
    return report


# --- Messages -----------------------------------------------------------


@dataclass
class SendResult:
    sent: list[int] = field(default_factory=list)
    on_leave: list[int] = field(default_factory=list)
    recently_messaged: list[int] = field(default_factory=list)
    nothing_to_fix: list[int] = field(default_factory=list)
    no_discord: list[int] = field(default_factory=list)


def message_context(sender_name: str, characters: list[str]) -> dict:
    return {
        "sender": sender_name,
        "first": characters[0] if characters else "",
        "others": max(len(characters) - 1, 0),
    }


def send_messages(
    sender, user_ids: Iterable[int], now: Optional[datetime] = None
) -> SendResult:
    """DM each pilot once about the characters they need to re-add.

    Skips pilots On Leave, pilots messaged in the last week, pilots with no
    Discord linked and pilots with nothing left to fix. Sent whether or not the pilot turned task messages
    on: a superuser chose to send it.
    """
    # pylint: disable=import-outside-toplevel
    from notifications.service import notify_users
    from notifications.types.esi import ESI_MESSAGE_KEY

    now = now or timezone.now()
    user_ids = set(user_ids)
    result = SendResult()
    by_user = broken_characters_by_user(user_ids)
    statuses = _statuses(user_ids)
    recent = {
        user_id
        for user_id, sent_at in last_messages(user_ids).items()
        if sent_at > now - MESSAGE_COOLDOWN
    }
    players = {
        player.user_id: player
        for player in EvePlayer.objects.filter(
            user_id__in=user_ids
        ).select_related("primary_character", "user")
    }
    discord = set(
        DiscordUser.objects.filter(user_id__in=user_ids).values_list(
            "user_id", flat=True
        )
    )
    # As the superuser's preview shows it.
    sender_name = sender.username
    recipients, contexts = [], {}
    for user_id in sorted(user_ids):
        characters = by_user.get(user_id)
        if not characters:
            result.nothing_to_fix.append(user_id)
            continue
        if _on_leave(statuses.get(user_id)):
            result.on_leave.append(user_id)
            continue
        if user_id in recent:
            result.recently_messaged.append(user_id)
            continue
        if user_id not in discord:
            result.no_discord.append(user_id)
            continue
        player = players.get(user_id)
        main = player.primary_character if player else None
        names = [c.character_name for c in characters]
        if main and main.character_name in names:
            names.remove(main.character_name)
            names.insert(0, main.character_name)
        user = player.user if player else characters[0].user
        recipients.append(user)
        contexts[user_id] = message_context(sender_name, names)
        EsiMessage.objects.create(
            user_id=user_id, sent_by=sender, characters=len(names)
        )
        result.sent.append(user_id)
    if recipients:
        notify_users(
            recipients,
            ESI_MESSAGE_KEY,
            {"sender": sender_name},
            idempotency_key=f"{ESI_MESSAGE_KEY}:{now:%Y%m%d%H%M%S}",
            stagger_rate_limited_channels=True,
            user_contexts=contexts,
        )
    return result
