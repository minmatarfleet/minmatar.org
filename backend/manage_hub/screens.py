"""Which Manage hub screens a user may reach.

Each screen opens with the site gate its page uses (frontend/app/src/json/
feature_gates.json), decided here the way src/helpers/gates.ts decides it
for the current FRONTEND_GATE_SOURCE, or with the backend check the page
asks the API for (LP desk, alliance health).

The backend image ships without the frontend, so the gates the hub needs
are copied below. tests.py fails when they drift from feature_gates.json or
from the hub's own registry (frontend/app/src/json/manage_screens.json).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from alliance.helpers.access import can_view_health
from groups.helpers.feature_access import get_user_feature_codes
from industry.endpoints.loyalty.auth_helpers import can_manage_buyback
from users.endpoints.get_me_gates import frontend_gate_source
from users.helpers import get_user_permissions


@dataclass(frozen=True)
class HubGate:
    """A feature_gates.json entry: the feature and its legacy expression."""

    feature: str
    perms: tuple[str, ...] = ()
    superuser: bool = True
    # Legacy check supplied by code (feature_gates.json `legacy.custom`).
    custom: bool = False


GATES: dict[str, HubGate] = {
    "campaigns.manage": HubGate(
        "campaigns.manage", ("campaigns.change_campaign",)
    ),
    "fleets.npsi_sources.manage": HubGate(
        "fleets.npsi_sources.manage", ("fleets.change_npsieventsource",)
    ),
    "structures.timers.correct": HubGate(
        "structures.timers.correct", ("structures.change_evestructuretimer",)
    ),
    "market.manage": HubGate(
        "market.manage", ("eveonline.change_evelocation",)
    ),
    "buyback.manage": HubGate(
        "buyback.manage", ("buyback.change_evebuybacksettings",)
    ),
    "freight.manage": HubGate(
        "freight.manage", ("freight.change_evefreightroute",)
    ),
    "help_tickets.manage": HubGate(
        "help_tickets.manage", ("help_tickets.change_helprequestcategory",)
    ),
    "posts.tags.manage": HubGate(
        "posts.tags.manage", ("posts.change_evetag",)
    ),
    "reddit.approvals.manage": HubGate(
        "reddit.approvals.manage",
        ("reddit.change_redditpostchangerequest",),
    ),
    "creators.moderate": HubGate(
        "creators.moderate", ("creators.change_creatoraccount",)
    ),
    "learning.manage": HubGate(
        "learning.manage", ("learning.change_certificate",)
    ),
    "skillsets.manage": HubGate(
        "skillsets.manage", ("eveonline.change_eveskillset",)
    ),
    "fittings.doctrine.edit": HubGate(
        "fittings.doctrine.propose", (), superuser=False, custom=True
    ),
    "srp.programs.manage": HubGate(
        "srp.programs.manage", ("srp.change_shipreimbursementprogram",)
    ),
    "surveys.manage": HubGate(
        "surveys.manage", ("surveys.change_surveycampaign",)
    ),
}


@dataclass(frozen=True)
class Screen:
    key: str
    group: str
    # A key of GATES, or empty when `check` decides.
    gate: str = ""
    # A key of CHECKS: the backend answer the page itself asks for.
    check: str = ""


# Display order, as in manage_screens.json.
SCREENS: tuple[Screen, ...] = (
    Screen("campaigns", "fleets", gate="campaigns.manage"),
    Screen("payout_codes", "fleets", gate="campaigns.manage"),
    Screen("npsi_feeds", "fleets", gate="fleets.npsi_sources.manage"),
    Screen("structure_timers", "fleets", gate="structures.timers.correct"),
    Screen("market_hubs", "market", gate="market.manage"),
    Screen("buyback", "market", gate="buyback.manage"),
    Screen("freight_routes", "market", gate="freight.manage"),
    Screen("lp_desk", "market", check="lp_desk"),
    Screen("help_tickets", "content", gate="help_tickets.manage"),
    Screen("post_tags", "content", gate="posts.tags.manage"),
    Screen("reddit", "content", gate="reddit.approvals.manage"),
    Screen("creators", "content", gate="creators.moderate"),
    Screen("guides", "learning", gate="learning.manage"),
    Screen("certificates", "learning", gate="learning.manage"),
    Screen("onboarding", "learning", gate="learning.manage"),
    Screen("skillsets", "learning", gate="skillsets.manage"),
    Screen("doctrines", "ships", gate="fittings.doctrine.edit"),
    Screen("srp_amounts", "ships", gate="srp.programs.manage"),
    Screen("alliance_health", "people", check="alliance_health"),
    Screen("surveys", "people", gate="surveys.manage"),
)

# Pages that ask the API instead of a site gate, by the check they ask.
CHECKS = {
    "lp_desk": can_manage_buyback,
    "alliance_health": can_view_health,
}


class GateEvaluator:
    """One user's site gates, decided the way src/helpers/gates.ts does."""

    def __init__(self, user):
        self.user = user
        self.source = frontend_gate_source()

    @cached_property
    def permissions(self) -> set[str]:
        return set(get_user_permissions(self.user.id))

    @cached_property
    def features(self) -> set[str]:
        return set(get_user_feature_codes(self.user))

    def allows(self, gate_key: str) -> bool:
        gate = GATES[gate_key]
        if self.source == "features":
            return gate.feature in self.features
        if gate.custom:
            # fittings.doctrine.edit (helpers/doctrine_editor.ts): the
            # superuser claim or the pilot feature.
            return self.user.is_superuser or gate.feature in self.features
        if gate.superuser and self.user.is_superuser:
            return True
        return any(perm in self.permissions for perm in gate.perms)

    def can_reach(self, screen: Screen) -> bool:
        if screen.check:
            return bool(CHECKS[screen.check](self.user))
        return self.allows(screen.gate)


def _signed_in(user) -> bool:
    return user is not None and getattr(user, "is_authenticated", False)


def reachable_screens(user) -> list[Screen]:
    if not _signed_in(user):
        return []
    evaluator = GateEvaluator(user)
    return [screen for screen in SCREENS if evaluator.can_reach(screen)]


def can_reach_any(user) -> bool:
    if not _signed_in(user):
        return False
    evaluator = GateEvaluator(user)
    return any(evaluator.can_reach(screen) for screen in SCREENS)
