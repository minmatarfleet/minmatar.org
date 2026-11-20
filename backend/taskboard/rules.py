"""Automatic tasks: what opens one, for whom, and what it says.

Each rule collects the things that should have an open task right now.
``taskboard.sync`` opens a task for each new thing, refreshes the text of
the ones still there, and closes the ones that are gone, so a task closes
by itself once the pilot fixes what it is about.

Links are site paths; the website adds its own origin and language.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Iterable, Optional

from django.db import models

from django.db.models import Count, Min, Q
from django.utils import timezone

from applications.models import EveCorporationApplication
from esi_health.models import ScopeRollout
from esi_health.services import (
    DIRECTOR_MISSING,
    DIRECTOR_OK,
    asked_rollouts,
    director_statuses,
    missing_rollouts,
    needs_readd_q,
    token_scopes,
)
from eveonline.helpers.alliances import alliance_corporations
from eveonline.helpers.characters.identity import owned_by_q
from eveonline.models import (
    EveCharacter,
    EveCorporation,
    EvePlayer,
    FwPayoutEventCode,
)
from fittings.models import EveDoctrineChangeRequest, EveFittingChangeRequest
from fleets.models import EveFleetInvite, NpsiEventSource
from manage_hub.summary import npsi_feeds, payout_codes, reddit_posts
from reddit.models import RedditPostChangeRequest, RedditPostTemplate
from taskboard.models import TeamKind, Weight
from tribes.models import (
    TribeGroup,
    TribeGroupInvitation,
    TribeGroupMembership,
)

AUDIENCE_PILOT = "pilot"
AUDIENCE_CHIEF = "chief"
AUDIENCE_CEO = "ceo"
AUDIENCE_STAFF = "staff"
AUDIENCES = (AUDIENCE_PILOT, AUDIENCE_CHIEF, AUDIENCE_CEO, AUDIENCE_STAFF)


@dataclass
class Item:
    """One thing that should have an open task."""

    source_key: str
    title: str
    detail: str = ""
    link_url: str = ""
    link_label: str = ""
    # A pilot's own task...
    user_id: Optional[int] = None
    # ...or work shared by a team until someone takes it.
    team_kind: str = ""
    team_id: Optional[int] = None
    team_role: str = ""
    team_label: str = ""
    # When the thing started waiting, when the site knows.
    since: Optional[datetime] = None


@dataclass(frozen=True)
class Rule:
    code: str
    # Settings and team views name the rule with these.
    label: str
    description: str
    audience: str
    weight: str
    # collect(user_ids): the items that should be open now. user_ids limits
    # a pilot rule to those users (a quick refresh when a pilot opens their
    # list); team rules ignore it.
    collect: Callable[[Optional[set[int]]], list[Item]]
    stop_after_days: Optional[int] = None
    claim_expires_days: Optional[int] = None
    # Saving or deleting a row of these models re-runs a team rule straight
    # away (taskboard.signals), so its task closes when the work is done
    # instead of at the next 15-minute sync.
    watch: tuple[type[models.Model], ...] = ()

    @property
    def is_pilot_rule(self) -> bool:
        return self.audience == AUDIENCE_PILOT


def _limit(queryset, field: str, user_ids: Optional[set[int]]):
    if user_ids is None:
        return queryset
    return queryset.filter(**{f"{field}__in": user_ids})


# --- Pilot rules -------------------------------------------------------


def _names(names: list[str], shown: int = 3) -> str:
    if len(names) <= shown:
        return ", ".join(names)
    return f"{', '.join(names[:shown])} and {len(names) - shown} more"


def collect_reauth_character(user_ids: Optional[set[int]]) -> list[Item]:
    """One task for a broken main, one for all the broken alts.

    A pilot with nine broken characters gets two tasks, not nine. The main's
    task keeps the old per-character key, so it carries over.
    """
    rows = (
        _limit(
            EveCharacter.objects.filter(needs_readd_q()), "user_id", user_ids
        )
        .order_by("character_name")
        .values_list("user_id", "character_id", "character_name")
    )
    by_user: dict[int, list[tuple[int, str]]] = {}
    for user_id, character_id, name in rows:
        by_user.setdefault(user_id, []).append(
            (character_id, name or str(character_id))
        )
    mains = dict(
        EvePlayer.objects.filter(
            user_id__in=list(by_user), primary_character__isnull=False
        ).values_list("user_id", "primary_character__character_id")
    )
    items = []
    for user_id, characters in by_user.items():
        main_id = mains.get(user_id)
        alts = [
            name
            for character_id, name in characters
            if character_id != main_id
        ]
        main = next(
            (
                name
                for character_id, name in characters
                if character_id == main_id
            ),
            None,
        )
        if main:
            items.append(
                Item(
                    source_key=f"character:{main_id}",
                    user_id=user_id,
                    title=f"Re-add {main}",
                    detail="Your main · EVE stopped letting us read it",
                    link_url=f"/account/?readd={main_id}",
                    link_label="Re-add",
                )
            )
        if alts:
            count = len(alts)
            items.append(
                Item(
                    source_key="alts",
                    user_id=user_id,
                    title=(
                        f"Re-add {alts[0]}"
                        if count == 1
                        else f"Re-add {count} {'alts' if main_id else 'characters'}"
                    ),
                    detail=(
                        "EVE stopped letting us read it"
                        if count == 1
                        else _names(alts)
                    ),
                    link_url="/account/?readd=alts",
                    link_label="Re-add",
                )
            )
    return items


def collect_update_scopes(user_ids: Optional[set[int]]) -> list[Item]:
    """Working tokens missing a scope a superuser asks for (ESI health)."""
    rollouts = asked_rollouts()
    if not rollouts:
        return []
    characters = list(
        _limit(
            EveCharacter.objects.filter(
                user__isnull=False, token__isnull=False, esi_suspended=False
            ),
            "user_id",
            user_ids,
        ).only(
            "user_id",
            "character_name",
            "token_id",
            "esi_suspended",
            "esi_scope_groups",
            "esi_token_level",
        )
    )
    scopes = token_scopes(c.token_id for c in characters)
    by_user: dict[int, list[str]] = {}
    labels: dict[int, set[str]] = {}
    for character in characters:
        missing = missing_rollouts(
            character, scopes.get(character.token_id, set()), rollouts
        )
        if not missing:
            continue
        by_user.setdefault(character.user_id, []).append(
            character.character_name
        )
        labels.setdefault(character.user_id, set()).update(
            rollout.label for rollout in missing
        )
    items = []
    for user_id, names in by_user.items():
        count = len(names)
        adds = " and ".join(sorted(labels[user_id]))
        items.append(
            Item(
                source_key="scopes",
                user_id=user_id,
                title=(
                    f"Update ESI on {names[0]}"
                    if count == 1
                    else f"Update ESI on {count} characters"
                ),
                detail=f"A newer login adds {adds}",
                link_url="/account/",
                link_label="Update",
            )
        )
    return items


def collect_pick_main(user_ids: Optional[set[int]]) -> list[Item]:

    with_characters = set(
        _limit(
            EveCharacter.objects.filter(user__isnull=False),
            "user_id",
            user_ids,
        ).values_list("user_id", flat=True)
    )
    with_main = set(
        EvePlayer.objects.filter(
            user_id__in=with_characters, primary_character__isnull=False
        ).values_list("user_id", flat=True)
    )
    return [
        Item(
            source_key="main",
            user_id=user_id,
            title="Pick your main character",
            detail="Leaders and fleet tools show you by your main",
            link_url="/account/",
            link_label="Pick main",
        )
        for user_id in sorted(with_characters - with_main)
    ]


def collect_fleet_invite(user_ids: Optional[set[int]]) -> list[Item]:

    now = timezone.now()
    invites = _limit(
        EveFleetInvite.objects.filter(
            answer=EveFleetInvite.ANSWER_PENDING,
            eve_fleet__start_time__gt=now,
        ),
        "user_id",
        user_ids,
    ).select_related("eve_fleet", "eve_fleet__created_by")
    items = []
    for invite in invites:
        fleet = invite.eve_fleet
        fc = fleet.created_by.username if fleet.created_by else ""
        items.append(
            Item(
                source_key=f"fleet:{fleet.pk}",
                user_id=invite.user_id,
                title=f"Answer your {fleet.get_type_display()} fleet invite",
                detail=f"{fc} invited you" if fc else "You were invited",
                link_url=f"/fleets/upcoming/{fleet.pk}",
                link_label="Answer",
                since=invite.sent_at or invite.created_at,
            )
        )
    return items


def collect_tribe_invitation(user_ids: Optional[set[int]]) -> list[Item]:

    now = timezone.now()
    invitations = _limit(
        TribeGroupInvitation.objects.filter(
            status=TribeGroupInvitation.STATUS_PENDING, expires_at__gt=now
        ),
        "user_id",
        user_ids,
    ).select_related("tribe_group", "invited_by")
    items = []
    for invitation in invitations:
        group = invitation.tribe_group
        inviter = (
            invitation.invited_by.username if invitation.invited_by else ""
        )
        items.append(
            Item(
                source_key=f"invitation:{invitation.pk}",
                user_id=invitation.user_id,
                title=f"Answer your invitation to {group.name}",
                detail=f"{inviter} invited you" if inviter else "",
                link_url=f"/alliance/tribes/{group.tribe_id}/{group.pk}/",
                link_label="Open invite",
                since=invitation.created_at,
            )
        )
    return items


def collect_set_timezone(user_ids: Optional[set[int]]) -> list[Item]:
    """Pilots with a main but no declared prime time (EvePlayer.prime_time,
    which the timezones app reads as the declared timezone)."""

    players = _limit(
        EvePlayer.objects.filter(
            user__isnull=False, primary_character__isnull=False
        ).filter(Q(prime_time__isnull=True) | Q(prime_time="")),
        "user_id",
        user_ids,
    ).values_list("user_id", flat=True)
    return [
        Item(
            source_key="timezone",
            user_id=user_id,
            title="Set your timezone",
            detail="Fleet invites follow the hours you play",
            link_label="Set timezone",
        )
        for user_id in players
    ]


# --- Team rules ----------------------------------------------------------


def _users_with_characters(user_ids: set[int]) -> set[int]:
    """The users among these who own at least one character."""
    found = set()
    for row in EveCharacter.objects.filter(owned_by_q(user_ids)).values(
        "user_id", "token__user_id"
    ):
        found.add(row["user_id"] or row["token__user_id"])
    return found


def collect_review_applications(user_ids=None) -> list[Item]:
    del user_ids  # a team rule collects for everyone

    # An account with no characters can't join a corporation: its
    # application is left-over data, not work for a recruiter.
    pending_users = set(
        EveCorporationApplication.objects.filter(status="pending").values_list(
            "user_id", flat=True
        )
    )
    rows = list(
        EveCorporationApplication.objects.filter(status="pending")
        .filter(user_id__in=_users_with_characters(pending_users))
        .order_by()
        .values("corporation_id")
        .annotate(n=Count("id"), first=Min("created_at"))
    )
    names = dict(
        EveCorporation.objects.filter(
            corporation_id__in=[row["corporation_id"] for row in rows]
        ).values_list("corporation_id", "name")
    )
    items = []
    for row in rows:
        corporation_id = row["corporation_id"]
        name = names.get(corporation_id, str(corporation_id))
        count = row["n"]
        items.append(
            Item(
                source_key=f"corporation:{corporation_id}",
                title=(
                    f"Review {count} application{'s' if count != 1 else ''}"
                    f" to {name}"
                ),
                link_url="/alliance/corporations/applications/",
                link_label="Review",
                team_kind=TeamKind.CORPORATION,
                team_id=corporation_id,
                team_role="recruiters",
                team_label=name,
                since=row["first"],
            )
        )
    return items


def _corporation_item(corporation, **fields) -> Item:
    return Item(
        source_key=f"corporation:{corporation['corporation_id']}",
        team_kind=TeamKind.CORPORATION,
        team_id=corporation["corporation_id"],
        team_role="leaders",
        team_label=corporation["name"],
        **fields,
    )


def collect_corp_director_token(user_ids=None) -> list[Item]:
    """A corporation whose best director token is missing or out of date.

    Out of date means it lacks a Director scope we read, less scopes added
    later that ESI health doesn't require yet.
    """
    del user_ids  # a team rule collects for everyone

    corporations = list(
        alliance_corporations().values("corporation_id", "name")
    )
    statuses = director_statuses(
        [row["corporation_id"] for row in corporations]
    )
    labels = dict(ScopeRollout.objects.values_list("scope", "label"))
    items = []
    for corporation in corporations:
        status = statuses[corporation["corporation_id"]]
        if status.state == DIRECTOR_OK:
            continue
        members_url = (
            f"/alliance/corporations/{corporation['corporation_id']}/#members"
        )
        if status.state == DIRECTOR_MISSING:
            items.append(
                _corporation_item(
                    corporation,
                    title="Add a director token",
                    detail="The member list stops updating without one",
                    link_url=members_url,
                    link_label="Add",
                )
            )
            continue
        uses = sorted(
            {labels[s] for s in status.missing_scopes if s in labels}
        )
        items.append(
            _corporation_item(
                corporation,
                title="Update the director token",
                detail=(
                    f"{' and '.join(uses).capitalize()} can't be read"
                    if uses
                    else "It's missing permissions we read"
                ),
                link_url=members_url,
                link_label="Update",
            )
        )
    return items


def collect_corp_unlinked(user_ids=None) -> list[Item]:
    """Characters in a corporation that nobody added to the site.

    They have no account, so only the corporation's leaders can reach them.
    """
    del user_ids  # a team rule collects for everyone

    corporations = {
        row["corporation_id"]: row
        for row in alliance_corporations().values("corporation_id", "name")
    }
    rows = (
        EveCharacter.objects.filter(
            corporation_id__in=list(corporations),
            user__isnull=True,
            token__isnull=True,
        )
        .order_by()
        .values("corporation_id")
        .annotate(n=Count("id"))
    )
    items = []
    for row in rows:
        corporation = corporations[row["corporation_id"]]
        count = row["n"]
        items.append(
            _corporation_item(
                corporation,
                title=(
                    f"Mail {count} character{'s' if count != 1 else ''} "
                    "with no account here"
                ),
                detail="Only leaders can reach them",
                link_url=(
                    "/alliance/corporations/"
                    f"{corporation['corporation_id']}/#members"
                ),
                link_label="See names",
            )
        )
    return items


def collect_review_join_requests(user_ids=None) -> list[Item]:
    del user_ids  # a team rule collects for everyone

    rows = list(
        TribeGroupMembership.objects.filter(status="pending")
        .order_by()
        .values("tribe_group_id")
        .annotate(n=Count("id"), first=Min("created_at"))
    )
    groups = TribeGroup.objects.in_bulk(
        [row["tribe_group_id"] for row in rows]
    )
    items = []
    for row in rows:
        group = groups.get(row["tribe_group_id"])
        if group is None:
            continue
        count = row["n"]
        items.append(
            Item(
                source_key=f"tribe_group:{group.pk}",
                title=(
                    f"Review {count} request{'s' if count != 1 else ''}"
                    f" to join {group.name}"
                ),
                link_url=(
                    f"/alliance/tribes/{group.tribe_id}/{group.pk}/members"
                ),
                link_label="Review",
                team_kind=TeamKind.TRIBE_GROUP,
                team_id=group.pk,
                team_role="leaders",
                team_label=group.name,
                since=row["first"],
            )
        )
    return items


def _staff_item(
    screen: str, title: str, detail: str, link: str, label: str, since
) -> Item:
    return Item(
        source_key=f"screen:{screen}",
        title=title,
        detail=detail,
        link_url=link,
        link_label=label,
        team_kind=TeamKind.STAFF,
        team_role=screen,
        team_label="",
        since=since,
    )


def collect_doctrine_changes(user_ids=None) -> list[Item]:
    del user_ids  # a team rule collects for everyone

    count = 0
    first = None
    for model in (EveDoctrineChangeRequest, EveFittingChangeRequest):
        row = model.objects.filter(status="pending").aggregate(
            n=Count("id"), first=Min("submitted_at")
        )
        count += row["n"] or 0
        if row["first"] and (first is None or row["first"] < first):
            first = row["first"]
    if not count:
        return []
    return [
        _staff_item(
            "doctrines",
            f"Review {count} doctrine change{'s' if count != 1 else ''}",
            "",
            "/ships/doctrines/review/",
            "Review",
            first,
        )
    ]


def collect_reddit_posts(user_ids=None) -> list[Item]:
    del user_ids  # a team rule collects for everyone

    queue = reddit_posts()
    if not queue.count:
        return []
    return [
        _staff_item(
            "reddit",
            f"Approve {queue.count} Reddit post"
            f"{'s' if queue.count != 1 else ''}",
            f"{queue.next_label} is next" if queue.next_label else "",
            "/alliance/reddit-review/",
            "Review",
            queue.oldest_at,
        )
    ]


def collect_payout_codes(user_ids=None) -> list[Item]:
    del user_ids  # a team rule collects for everyone

    queue = payout_codes()
    if not queue.count:
        return []
    return [
        _staff_item(
            "payout_codes",
            f"Map {queue.count} new payout code"
            f"{'s' if queue.count != 1 else ''}",
            f"Code {queue.next_label} is the oldest",
            "/campaigns/event-codes/",
            "Map codes",
            queue.oldest_at,
        )
    ]


def collect_npsi_feeds(user_ids=None) -> list[Item]:
    del user_ids  # a team rule collects for everyone

    queue = npsi_feeds()
    if not queue.count:
        return []
    title = (
        f"Fix the {queue.next_label} calendar feed"
        if queue.count == 1 and queue.next_label
        else f"Fix {queue.count} calendar feeds"
    )
    return [
        _staff_item(
            "npsi_feeds",
            title,
            "It stopped reading",
            "/fleets/npsi-sources/",
            "Open feeds",
            queue.oldest_at,
        )
    ]


RULES: dict[str, Rule] = {
    rule.code: rule
    for rule in (
        Rule(
            "reauth_character",
            "Re-add a character",
            "Opens when a character's ESI token stops working or is gone: "
            "one task for the main, one for the alts",
            AUDIENCE_PILOT,
            Weight.NEEDS_YOU,
            collect_reauth_character,
        ),
        Rule(
            "update_scopes",
            "Update ESI",
            "Opens when a working token lacks a scope ESI health asks for",
            AUDIENCE_PILOT,
            Weight.SUGGESTION,
            collect_update_scopes,
            stop_after_days=30,
        ),
        Rule(
            "pick_main",
            "Pick a main character",
            "Opens when an account has characters but no main",
            AUDIENCE_PILOT,
            Weight.NEEDS_YOU,
            collect_pick_main,
        ),
        Rule(
            "fleet_invite",
            "Answer a fleet invite",
            "Opens when an FC invites the pilot",
            AUDIENCE_PILOT,
            Weight.NEEDS_YOU,
            collect_fleet_invite,
        ),
        Rule(
            "tribe_invitation",
            "Answer a group invitation",
            "Opens when a chief invites the pilot to a tribe group",
            AUDIENCE_PILOT,
            Weight.NEEDS_YOU,
            collect_tribe_invitation,
        ),
        Rule(
            "set_timezone",
            "Set your timezone",
            "Opens when no timezone is on record",
            AUDIENCE_PILOT,
            Weight.SUGGESTION,
            collect_set_timezone,
            stop_after_days=30,
        ),
        Rule(
            "review_join_requests",
            "Review requests to join a group",
            "Opens when pilots ask to join a tribe group",
            AUDIENCE_CHIEF,
            Weight.NEEDS_YOU,
            collect_review_join_requests,
            claim_expires_days=14,
            watch=(TribeGroupMembership,),
        ),
        Rule(
            "review_applications",
            "Review applications",
            "Opens when pilots apply to a corporation",
            AUDIENCE_CEO,
            Weight.NEEDS_YOU,
            collect_review_applications,
            claim_expires_days=14,
            watch=(EveCorporationApplication,),
        ),
        Rule(
            "corp_director_token",
            "Fix the director token",
            "Opens when a corporation has no director token, or its best one "
            "lacks a permission we read",
            AUDIENCE_CEO,
            Weight.NEEDS_YOU,
            collect_corp_director_token,
            claim_expires_days=14,
        ),
        Rule(
            "corp_unlinked",
            "Reach characters with no account",
            "Opens when characters in a corporation have no account here",
            AUDIENCE_CEO,
            Weight.SUGGESTION,
            collect_corp_unlinked,
            claim_expires_days=14,
        ),
        Rule(
            "review_doctrine_changes",
            "Review doctrine changes",
            "Opens when a doctrine or fitting change is sent for review",
            AUDIENCE_STAFF,
            Weight.NEEDS_YOU,
            collect_doctrine_changes,
            claim_expires_days=14,
            watch=(EveDoctrineChangeRequest, EveFittingChangeRequest),
        ),
        Rule(
            "approve_reddit_posts",
            "Approve Reddit posts",
            "Opens when a corporation's Reddit post waits for approval",
            AUDIENCE_STAFF,
            Weight.NEEDS_YOU,
            collect_reddit_posts,
            claim_expires_days=14,
            watch=(RedditPostChangeRequest, RedditPostTemplate),
        ),
        Rule(
            "map_payout_codes",
            "Map new payout codes",
            "Opens when a campaign payout code has no meaning yet",
            AUDIENCE_STAFF,
            Weight.NEEDS_YOU,
            collect_payout_codes,
            claim_expires_days=14,
            watch=(FwPayoutEventCode,),
        ),
        Rule(
            "fix_calendar_feeds",
            "Fix a calendar feed",
            "Opens when an NPSI calendar feed fails to read",
            AUDIENCE_STAFF,
            Weight.NEEDS_YOU,
            collect_npsi_feeds,
            claim_expires_days=14,
            watch=(NpsiEventSource,),
        ),
    )
}


def pilot_rules() -> Iterable[Rule]:
    return (rule for rule in RULES.values() if rule.is_pilot_rule)


def stop_after(rule: Rule, setting) -> Optional[timedelta]:
    days = setting.stop_after_days if setting else rule.stop_after_days
    return timedelta(days=days) if days else None


def claim_expiry(rule: Optional[Rule], setting) -> Optional[timedelta]:
    if setting and setting.claim_expires_days:
        return timedelta(days=setting.claim_expires_days)
    if rule and rule.claim_expires_days:
        return timedelta(days=rule.claim_expires_days)
    return None
