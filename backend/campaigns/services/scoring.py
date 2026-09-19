"""Turn a pilot's day of activity into points.

Two rules shape every weight. This is a fleet alliance, so kill points scale
down with the number of enlisted pilots on the mail and a lone hunter is not
out-earned by a blob. And a day never goes negative, so a bad night never
punishes someone for undocking.
"""

from __future__ import annotations

from campaigns.constants import COMPLEX_TIER_POINTS, DEFAULT_SCORING
from campaigns.models import SiteKind


def weights(campaign) -> dict:
    merged = dict(DEFAULT_SCORING)
    merged.update(campaign.scoring or {})
    return merged


def kill_points(
    campaign,
    *,
    enlisted_on_mail: int,
    final_blow: bool = False,
    solo: bool = False,
    in_fleet: bool = False,
    isk_value: int = 0,
) -> int:
    """Points for one kill for one pilot on the mail."""
    w = weights(campaign)
    scale = min(1.0, w["kill_scale_cap"] / max(enlisted_on_mail, 1))
    points = w["kill_base"] * scale

    if final_blow:
        points += w["final_blow_bonus"]
    if solo:
        points += w["solo_bonus"]
    if in_fleet:
        points += w["fleet_kill_bonus"]
    if 2 <= enlisted_on_mail <= w["gang_size_max"]:
        points += w["gang_kill_bonus"]

    isk_points = (isk_value / w["isk_per_point"]) * scale
    points += min(isk_points, w["isk_points_cap_per_kill"])

    return int(round(points))


def loss_points(campaign, *, in_fleet_or_gang: bool) -> int:
    w = weights(campaign)
    return (
        w["loss_penalty_in_fleet"] if in_fleet_or_gang else w["loss_penalty"]
    )


def site_points(
    campaign,
    *,
    site_kind: str,
    base_lp_tier: int | None = None,
    primary_system: bool = False,
    index_today: int = 0,
) -> int:
    """Points for one site completion.

    Complexes score off the recovered base tier, never off a guessed class
    name, and an unknown tier scores as the smallest complex.
    """
    w = weights(campaign)

    if site_kind == SiteKind.COMPLEX:
        tier_points = COMPLEX_TIER_POINTS.get(
            base_lp_tier, COMPLEX_TIER_POINTS[10_000]
        )
        points = w["complex_base"] + tier_points
    elif site_kind in (
        SiteKind.ADVANTAGE_SITE,
        SiteKind.RENDEZVOUS_POINT,
        SiteKind.PROPAGANDA_BEACON,
        SiteKind.LISTENING_OUTPOST,
    ):
        points = w["advantage_site"]
    elif site_kind == SiteKind.SUPPLY_CACHE:
        points = w["supply_cache"]
    elif site_kind == SiteKind.BATTLEFIELD:
        points = w["battlefield"]
    else:
        return 0

    if primary_system:
        points += w["primary_system_bonus"]

    # Soft cap: the first sites of a day score in full, the rest at half.
    if index_today >= w["site_soft_cap"]:
        points = points / 2

    return int(round(points))


def day_multiplier(campaign, hour_utc: int) -> float:
    """Off-peak work is worth more; nobody else is holding those hours."""
    w = weights(campaign)
    if hour_utc in w["off_peak_hours"]:
        return w["off_peak_multiplier"]
    return 1.0


def streak_points(campaign, streak_days: int) -> int:
    w = weights(campaign)
    if streak_days < 3:
        return 0
    return int(min(w["streak_per_day"] * (streak_days - 2), w["streak_cap"]))


def contribution_mix_bonus(campaign, ways_scored: int) -> float:
    """A bonus for doing three different things in a week, supply included."""
    w = weights(campaign)
    return w["contribution_mix_bonus"] if ways_scored >= 3 else 0.0
