"""Site completions from Faction Warfare LP payout notifications.

ESI has no site-completion endpoint. The militia corporation sends a
character notification for every LP payout, and that notification is the only
per-pilot record that a complex, advantage site, supply cache or battlefield
was completed. Complex class is then recovered from the amount.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from campaigns.constants import (
    ADVANTAGE_SITE_LP,
    EVENT_CODE_SEED,
    COMPLEX_BASE_TIERS,
    OPERATIONAL_STATE_MULTIPLIER,
    SUPPLY_CACHE_LP,
    SUPPRESSION_MULTIPLIER,
    TIER_TOLERANCE,
)
from campaigns.helpers import CampaignRoster, counting_campaigns
from campaigns.models import (
    CampaignComplexCompletion,
    CampaignSiteCompletion,
    CampaignSystem,
    CampaignSystemInsurgency,
    CampaignSystemSnapshot,
    OperationalState,
    SiteKind,
)
from eveonline.models import EveCharacterFwLpPayout, FwPayoutEventCode

logger = logging.getLogger(__name__)

# The notification body is YAML-ish text with one key per line.
_FIELD_RE = re.compile(r"^\s*(\w+):\s*(.+?)\s*$", re.MULTILINE)


def parse_payout_text(text: str) -> dict:
    """Parse a FacWarLPPayout* notification body into a dict."""
    fields: dict = {}
    for key, value in _FIELD_RE.findall(text or ""):
        value = value.strip()
        if value in ("null", "~", ""):
            fields[key] = None
            continue
        try:
            fields[key] = int(value)
        except ValueError:
            fields[key] = value.strip("'\"")
    return fields


# The columns these land in are 32- and 64-bit; anything larger is not a
# real payout, it is the format having changed under us.
MAX_INT_FIELD = 2**31 - 1
MAX_BIGINT_FIELD = 2**63 - 1


def _as_int(value, limit: int = MAX_BIGINT_FIELD) -> int | None:
    """Coerce a parsed notification field to something a column will take.

    The body is text CCP renders, so a field can arrive as a word, a float in
    exponent notation, or a number far larger than the column. None of that
    may take down the poll for every other character in the batch.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None
    if abs(number) > limit:
        return None
    return number


def store_payout(character, notification) -> EveCharacterFwLpPayout | None:
    """Store one FacWarLPPayout* notification. Idempotent on notification id."""
    if not isinstance(notification, dict):
        return None

    notification_type = notification.get("type") or ""
    if not notification_type.startswith("FacWarLPPayout"):
        return None

    notification_id = notification.get("notification_id")
    if notification_id is None:
        return None

    fields = parse_payout_text(notification.get("text") or "")
    timestamp = notification.get("timestamp") or timezone.now()

    notification_id = _as_int(notification_id)
    if notification_id is None:
        return None

    payout, _ = EveCharacterFwLpPayout.objects.update_or_create(
        notification_id=notification_id,
        defaults={
            "character": character,
            "notification_type": notification_type[:64],
            "occurred_at": timestamp,
            "amount_lp": _as_int(fields.get("amount"), MAX_INT_FIELD) or 0,
            "corp_id": _as_int(fields.get("corpID")),
            "event_code": _as_int(fields.get("event"), MAX_INT_FIELD),
            "location_id": _as_int(fields.get("locationID")),
            "ref_id": _as_int(fields.get("itemRefID")),
            "char_ref_id": _as_int(fields.get("charRefID")),
            "disqualification_type": str(
                fields.get("disqualificationType") or ""
            )[:64],
            "raw_text": (notification.get("text") or "")[:20000],
        },
    )
    return payout


def classify_payout(payout: EveCharacterFwLpPayout) -> tuple[str, bool]:
    """Return ``(site_kind, scorable)`` for a payout.

    An unconfirmed or unknown event code is stored and displayed but never
    scored, so a CCP change or a guess never inflates anyone's board.
    """
    code_row = FwPayoutEventCode.objects.filter(
        event_code=payout.event_code
    ).first()
    if not code_row:
        return SiteKind.UNKNOWN, False

    kind = code_row.site_kind

    # The advantage-site family splits on the amount, not the code.
    if kind == SiteKind.ADVANTAGE_SITE:
        if payout.amount_lp == SUPPLY_CACHE_LP:
            kind = SiteKind.SUPPLY_CACHE
        elif payout.amount_lp != ADVANTAGE_SITE_LP:
            return SiteKind.UNKNOWN, False

    return kind, bool(code_row.confirmed)


def attribute_payouts(payouts) -> dict:
    """Attribute stored payouts to campaigns, systems and pilots."""
    stats = {"attributed": 0, "skipped": 0, "unmapped": 0}
    # Rosters are small and change rarely; building one per payout would be a
    # query per row.
    rosters: dict[int, CampaignRoster] = {}

    for payout in payouts:
        if not payout.location_id:
            stats["skipped"] += 1
            continue

        kind, scorable = classify_payout(payout)
        if kind == SiteKind.KILL:
            # Kill payouts are the cross-check for missed kills, not a site.
            stats["skipped"] += 1
            continue
        if kind == SiteKind.UNKNOWN:
            stats["unmapped"] += 1

        for campaign in counting_campaigns(
            payout.location_id, payout.occurred_at
        ):
            if campaign.id not in rosters:
                rosters[campaign.id] = CampaignRoster(campaign)
            user = rosters[campaign.id].user_for(
                payout.character.character_id, payout.occurred_at
            )
            if user is None:
                continue
            campaign_system = CampaignSystem.objects.filter(
                campaign=campaign,
                solar_system_id=payout.location_id,
                retired_at__isnull=True,
            ).first()
            if not campaign_system:
                continue

            _, created = CampaignSiteCompletion.objects.update_or_create(
                payout=payout,
                defaults={
                    "campaign": campaign,
                    "user": user,
                    "character_id": payout.character.character_id,
                    "campaign_system": campaign_system,
                    "occurred_at": payout.occurred_at,
                    "amount_lp": payout.amount_lp,
                    "event_code": payout.event_code or 0,
                    "site_kind": kind,
                    "scored": scorable,
                },
            )
            if created:
                stats["attributed"] += 1

    return stats


# --- Complex class inference ----------------------------------------------


def suppression_multiplier(campaign_system, moment) -> float:
    row = (
        CampaignSystemInsurgency.objects.filter(
            campaign_system=campaign_system,
            valid_from__lte=moment,
        )
        .filter(
            _valid_until_q(moment),
        )
        .order_by("-valid_from")
        .first()
    )
    if not row:
        return 1.0
    return SUPPRESSION_MULTIPLIER.get(row.suppression_stage, 1.0)


def _valid_until_q(moment):
    return Q(valid_until__isnull=True) | Q(valid_until__gt=moment)


def contested_reading(campaign_system, moment) -> tuple[float, bool]:
    """``(multiplier, was_measured)`` for the contested share at a moment.

    CCP scales complex LP by how contested the system is. With no snapshot we
    fall back to 1.0 and say so, so the caller can refuse to claim confidence
    in a number it did not measure.
    """
    snapshot = (
        CampaignSystemSnapshot.objects.filter(
            campaign_system=campaign_system, captured_at__lte=moment
        )
        .order_by("-captured_at")
        .first()
    )
    if not snapshot:
        return 1.0, False
    return max(snapshot.contested_percent / 100.0, 0.01), True


def contested_factor(campaign_system, moment) -> float:
    return contested_reading(campaign_system, moment)[0]


def infer_complex_class(
    amount_lp: int,
    split_count: int,
    operational_state: str,
    contested: float,
    suppression: float,
    inputs_measured: bool = True,
) -> dict:
    """Recover the complex class from one pilot's share of the payout.

    ``amount = base x state_multiplier x contested x suppression / pilots``,
    so the base is recoverable when we know the other terms. Untracked pilots
    inside the plex make the split count a lower bound, so we try a few larger
    splits and report every tier that fits.

    ``inputs_measured`` is False when the operational state or the contested
    share was a fallback rather than a reading. A recovered tier is still
    worth storing then, but it can never be called certain.
    """
    state_multiplier = OPERATIONAL_STATE_MULTIPLIER.get(operational_state, 1.0)
    denominator = state_multiplier * contested * suppression
    if denominator <= 0 or amount_lp <= 0:
        return {
            "base_lp_tier": None,
            "candidates": [],
            "alternate_tiers": [],
            "confidence": "unknown",
            "split_used": split_count,
        }

    matches: list[tuple[int, int, tuple[str, ...]]] = []
    for extra in range(0, 4):
        pilots = split_count + extra
        implied_base = amount_lp * pilots / denominator
        for tier, classes in COMPLEX_BASE_TIERS.items():
            if abs(implied_base - tier) / tier <= TIER_TOLERANCE:
                matches.append((pilots, tier, classes))

    if not matches:
        return {
            "base_lp_tier": None,
            "candidates": [],
            "alternate_tiers": [],
            "confidence": "unknown",
            "split_used": split_count,
        }

    # The smallest split that fits is the most likely reading: untracked
    # pilots in the plex are the exception, not the rule.
    pilots, tier, classes = matches[0]
    alternates = sorted({match[1] for match in matches} - {tier})

    # Several base tiers are exact multiples of each other, so a solo 15,000
    # plex and a 30,000 plex shared with one untracked pilot produce the same
    # payout. When that is the case we say so rather than pick.
    confidence = (
        "high"
        if (
            inputs_measured
            and not alternates
            and len(classes) == 1
            and contested >= 0.05
        )
        else "low"
    )

    return {
        "base_lp_tier": tier,
        "candidates": list(classes),
        "alternate_tiers": alternates,
        "confidence": confidence,
        "split_used": pilots,
    }


def build_complex_completions(since_hours: int = 6) -> dict:
    """Group complex payouts by site instance and infer the class."""
    since = timezone.now() - timedelta(hours=since_hours)

    # Pilots in the same plex are polled at different times, so a second
    # payout for a site we have already grouped arrives on a later run. Every
    # site touched in the window is regrouped from all of its payouts, or the
    # split count would stay stuck at whatever the first poll saw.
    touched = set(
        CampaignSiteCompletion.objects.filter(
            site_kind=SiteKind.COMPLEX, occurred_at__gte=since
        ).values_list("campaign_id", "payout__ref_id")
    )
    touched = {(cid, ref) for cid, ref in touched if ref}
    if not touched:
        return {"groups": 0, "built": 0}

    rows = CampaignSiteCompletion.objects.filter(
        site_kind=SiteKind.COMPLEX,
        payout__ref_id__in=[ref for _, ref in touched],
    ).select_related("campaign", "campaign_system", "payout")

    groups: dict = {}
    for row in rows:
        key = (row.campaign_id, row.payout.ref_id)
        if key not in touched:
            continue
        groups.setdefault(key, []).append(row)

    built = 0
    for (campaign_id, site_ref), members in groups.items():
        # The model orders newest first; the capture happened at the earliest
        # payout, and every member of a split is paid the same amount.
        members.sort(key=lambda row: row.occurred_at)
        first = members[0]
        moment = first.occurred_at
        campaign_system = first.campaign_system
        snapshot = (
            CampaignSystemSnapshot.objects.filter(
                campaign_system=campaign_system, captured_at__lte=moment
            )
            .order_by("-captured_at")
            .first()
        )
        operational_state = (
            snapshot.operational_state if snapshot else "unknown"
        )
        contested, contested_measured = contested_reading(
            campaign_system, moment
        )
        suppression = suppression_multiplier(campaign_system, moment)

        inference = infer_complex_class(
            amount_lp=first.amount_lp,
            split_count=len(members),
            operational_state=operational_state,
            contested=contested,
            suppression=suppression,
            inputs_measured=(
                contested_measured
                and operational_state != OperationalState.UNKNOWN
            ),
        )

        with transaction.atomic():
            completion, _ = CampaignComplexCompletion.objects.update_or_create(
                campaign_id=campaign_id,
                site_ref=site_ref,
                defaults={
                    "campaign_system": campaign_system,
                    "completed_at": moment,
                    "split_count": inference["split_used"],
                    "operational_state": operational_state,
                    "contested_factor": contested,
                    "suppression_used": suppression,
                    "base_lp_tier": inference["base_lp_tier"],
                    # Only name the class when the reading is certain. A
                    # low-confidence row keeps its candidates and no name.
                    "inferred_plex_class": (
                        inference["candidates"][0]
                        if inference["confidence"] == "high"
                        and len(inference["candidates"]) == 1
                        else ""
                    ),
                    "class_candidates": inference["candidates"],
                    "confidence": inference["confidence"],
                },
            )
            CampaignSiteCompletion.objects.filter(
                id__in=[m.id for m in members]
            ).update(complex=completion)
        built += 1

    return {"groups": len(groups), "built": built}


def rescore_completions(event_code: int | None = None) -> dict:
    """Re-apply the event-code table to completions already recorded.

    Confirming a code is the whole point of the calibration table, so there
    has to be a way to make the sites it covers count without waiting for
    the next payout.
    """
    queryset = CampaignSiteCompletion.objects.select_related("payout")
    if event_code is not None:
        queryset = queryset.filter(event_code=event_code)

    changed = 0
    for completion in queryset.iterator():
        kind, scorable = classify_payout(completion.payout)
        if (kind, scorable) == (completion.site_kind, completion.scored):
            continue
        completion.site_kind = kind
        completion.scored = scorable
        completion.save(update_fields=["site_kind", "scored"])
        changed += 1

    return {"changed": changed}


def seed_event_codes() -> int:
    """Seed the calibration table. Never overwrites a human confirmation."""
    created = 0
    for row in EVENT_CODE_SEED:
        _, was_created = FwPayoutEventCode.objects.get_or_create(
            event_code=row["event_code"],
            defaults={
                "site_kind": row["site_kind"],
                "label": row["label"],
                "amount_rule": row["amount_rule"],
                "confirmed": row["confirmed"],
                "notes": row["notes"],
            },
        )
        created += int(was_created)
    return created
