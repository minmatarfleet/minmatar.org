"""Who belongs to which team, for shared tasks and the Team tab.

A team is a corporation, a tribe group, or a manage screen ("staff").
Membership is decided by the checks the rest of the site already uses:
corporation leaders and recruiters, tribe and group chiefs (with the
interim executor), and the gates of each manage screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Optional

from eveonline.helpers.corporations.applications import can_review_applications
from eveonline.helpers.corporations.permissions import can_manage_corporation
from eveonline.models import EveCorporation
from manage_hub.screens import reachable_screens
from tribes.helpers.permissions import user_can_manage_group
from tribes.models import Tribe, TribeGroup
from users.endpoints.get_me_gates import led_corporations
from taskboard.models import TeamKind


@dataclass(frozen=True)
class TeamRef:
    kind: str
    id: Optional[int]
    label: str
    # Group ids for a tribe: its members' tasks roll up to it.
    group_ids: tuple[int, ...] = field(default_factory=tuple)


class Membership:
    """One user's teams, worked out once per request."""

    def __init__(self, user):
        self.user = user

    @cached_property
    def staff_screens(self) -> set[str]:

        return {screen.key for screen in reachable_screens(self.user)}

    @cached_property
    def led_corporation_ids(self) -> set[int]:

        return {row.corporation_id for row in led_corporations(self.user.id)}

    def can_act(self, kind: str, team_id: Optional[int], role: str) -> bool:
        """May this user see and take a task shared by this team?"""
        user = self.user
        if not getattr(user, "is_authenticated", False):
            return False
        if kind == TeamKind.STAFF:
            return role in self.staff_screens
        if kind == TeamKind.CORPORATION:
            return self._corporation(team_id, role)
        if kind == TeamKind.TRIBE_GROUP:
            return self._group(team_id)
        return False

    def _corporation(self, corporation_id: Optional[int], role: str) -> bool:

        corporation = EveCorporation.objects.filter(
            corporation_id=corporation_id
        ).first()
        if corporation is None:
            return False
        if role == "recruiters":
            return can_review_applications(self.user, corporation)
        return can_manage_corporation(self.user, corporation)

    def _group(self, group_id: Optional[int]) -> bool:

        group = (
            TribeGroup.objects.select_related("tribe")
            .filter(pk=group_id)
            .first()
        )
        return bool(group) and user_can_manage_group(self.user, group)

    @cached_property
    def corporations(self) -> list[TeamRef]:
        """Corporations this user is CEO or a director of.

        Superusers too: an admin's Team tab lists the corporations they
        lead, not every corporation in the alliance.
        """
        rows = led_corporations(self.user.id)
        names = dict(
            EveCorporation.objects.filter(
                corporation_id__in=[row.corporation_id for row in rows]
            ).values_list("corporation_id", "name")
        )
        return sorted(
            (
                TeamRef(
                    TeamKind.CORPORATION,
                    row.corporation_id,
                    names.get(row.corporation_id, row.name),
                )
                for row in rows
            ),
            key=lambda team: team.label.lower(),
        )

    @cached_property
    def tribes(self) -> list[TeamRef]:
        """Tribes (with their groups) whose Team view this user sees.

        A group chief sees their group as a one-group tribe.
        """

        teams = []
        groups = list(
            TribeGroup.objects.select_related("tribe").order_by(
                "tribe__name", "name"
            )
        )
        by_tribe: dict[int, list] = {}
        for group in groups:
            by_tribe.setdefault(group.tribe_id, []).append(group)
        for tribe in Tribe.objects.order_by("name"):
            tribe_groups = by_tribe.get(tribe.pk, [])
            managed = [
                group
                for group in tribe_groups
                if user_can_manage_group(self.user, group)
            ]
            if not managed:
                continue
            whole = len(managed) == len(tribe_groups)
            teams.append(
                TeamRef(
                    "tribe",
                    tribe.pk if whole else managed[0].pk,
                    tribe.name if whole else managed[0].name,
                    tuple(group.pk for group in managed),
                )
            )
        return teams

    @property
    def leads_anything(self) -> bool:
        return bool(
            self.user.is_superuser
            or self.staff_screens
            or self.led_corporation_ids
            or self.tribes
        )


def can_assign(user) -> bool:
    """Leaders write tasks; everyone else only receives them."""
    if not getattr(user, "is_authenticated", False):
        return False
    return Membership(user).leads_anything
