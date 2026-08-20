"""Build the member auto-context block from cached platform data.

CRITICAL: this must never trigger a live ESI call — it reads only stored tables
so the survey stays fast. Every lookup is wrapped so a missing/unsynced record
degrades to a blank field rather than failing the whole context.
"""

import logging

from eveonline.helpers.characters import (
    user_characters,
    user_primary_character,
)
from eveonline.models import EveCorporation
from fleets.models import EveFleet, EveFleetInstanceMember
from groups.helpers.feature_access import user_community_status
from learning.helpers import completed_learning_ids
from learning.models import UserLearningPreference
from surveys.constants import (
    ACTIVITY_CORE,
    ACTIVITY_INACTIVE,
    ACTIVITY_LAPSING,
    ACTIVITY_REGULAR,
)
from surveys.helpers import standing
from surveys.helpers.corp_history import alliance_corp_history
from surveys.helpers.teams import member_tribe_rows
from surveys.helpers.tenure import (
    member_join_date,
    quarter_window,
    tenure_cohort,
    tenure_days,
)

logger = logging.getLogger(__name__)


def _character_ids(user) -> list[int]:
    try:
        return [c.character_id for c in user_characters(user)]
    except Exception:  # pragma: no cover - defensive
        return []


def _corp_context(user) -> dict:
    pc = None
    try:
        pc = user_primary_character(user)
    except Exception:  # pragma: no cover - defensive
        pc = None
    if not pc:
        return {
            "character_id": None,
            "character_name": "",
            "corporation_id": None,
            "corporation_name": "",
            "ceo_id": None,
            "ceo_name": "",
        }
    corp_name = ""
    ceo_id = None
    ceo_name = ""
    if pc.corporation_id:
        corp_obj = (
            EveCorporation.objects.filter(corporation_id=pc.corporation_id)
            .select_related("ceo")
            .first()
        )
        if corp_obj:
            corp_name = corp_obj.name or ""
            if corp_obj.ceo:
                ceo_id = corp_obj.ceo.character_id
                ceo_name = corp_obj.ceo.character_name
    return {
        "character_id": pc.character_id,
        "character_name": pc.character_name,
        "corporation_id": pc.corporation_id,
        "corporation_name": corp_name,
        "ceo_id": ceo_id,
        "ceo_name": ceo_name,
    }


def _prime_time(user) -> str:
    try:
        player = getattr(user, "eveplayer", None)
        return player.prime_time or "" if player else ""
    except Exception:  # pragma: no cover - defensive
        return ""


def _tribe_names(user) -> list[str]:
    try:
        memberships = user.tribe_memberships.filter(
            status="active"
        ).select_related("tribe_group__tribe")
        names = []
        for m in memberships:
            tg = m.tribe_group
            names.append(tg.name if tg else "")
        return [n for n in names if n]
    except Exception:  # pragma: no cover - defensive
        return []


def fleets_attended(user, start=None, end=None) -> int:
    """Distinct fleets attended by any of the user's characters in a window."""
    char_ids = _character_ids(user)
    if not char_ids:
        return 0
    if start is None or end is None:
        start, end = quarter_window()
    try:
        return (
            EveFleetInstanceMember.objects.filter(
                character_id__in=char_ids,
                join_time__range=(start, end),
            )
            .values("eve_fleet_instance__eve_fleet")
            .distinct()
            .count()
        )
    except Exception:  # pragma: no cover - defensive
        logger.debug("fleet participation lookup failed", exc_info=True)
        return 0


def _activity_tier(fleet_count: int) -> str:
    if fleet_count >= 10:
        return ACTIVITY_CORE
    if fleet_count >= 3:
        return ACTIVITY_REGULAR
    if fleet_count >= 1:
        return ACTIVITY_LAPSING
    return ACTIVITY_INACTIVE


def _role_flags(user) -> list[str]:
    flags = []
    try:
        if EveFleet.objects.filter(created_by=user).exists():
            flags.append("fc")
    except Exception:  # pragma: no cover - defensive
        pass
    if _tribe_names(user):
        flags.append("tribe_member")
    return flags


def community_status(user) -> str:
    try:
        return user_community_status(user) or ""
    except Exception:  # pragma: no cover - defensive
        return ""


def _learning_progress(user) -> dict:
    try:
        completed = list(completed_learning_ids(user))
        count = len(completed)
    except Exception:  # pragma: no cover - defensive
        count = 0
    persona = ""
    try:
        pref = getattr(user, "learningpreference", None)
        if pref is None:
            pref = UserLearningPreference.objects.filter(user=user).first()
        if pref:
            persona = pref.persona or ""
    except Exception:  # pragma: no cover - defensive
        persona = ""
    return {"guides_completed": count, "persona": persona}


def build_member_context(user) -> dict:
    """Return the identity/auto-context block for the survey fill-out screen."""
    corp = _corp_context(user)
    corp_hist = alliance_corp_history(user)
    days = tenure_days(user)
    fleet_count = fleets_attended(user)
    joined = member_join_date(user)
    learning = _learning_progress(user)
    tribes = member_tribe_rows(user)
    activity_tier = _activity_tier(fleet_count)
    prime = _prime_time(user)

    return {
        "tenure_note": standing.tenure_note(joined),
        "fleets_note": standing.fleets_note(activity_tier),
        "guides_note": standing.guides_note(learning["guides_completed"]),
        "timezone_note": standing.timezone_note(prime),
        "character_id": corp["character_id"],
        "character_name": corp["character_name"],
        "corporation_id": corp["corporation_id"],
        "corporation_name": corp["corporation_name"],
        "ceo_id": corp["ceo_id"],
        "ceo_name": corp["ceo_name"],
        "corp_history": corp_hist["corps"],
        "graduated": corp_hist["graduated"],
        "prime_time": _prime_time(user),
        "tribes": tribes,
        "tribe_names": [t["label"] for t in tribes],
        "community_status": community_status(user),
        "tenure_days": days,
        "tenure_cohort": tenure_cohort(days),
        "joined_at": joined.isoformat() if joined else None,
        "fleets_attended_quarter": fleet_count,
        "activity_tier": _activity_tier(fleet_count),
        "role_flags": _role_flags(user),
        "guides_completed": learning["guides_completed"],
        "persona": learning["persona"],
    }


def build_segmentation(user, context: dict | None = None) -> dict:
    """The subset of context frozen onto SurveyResponse for slicing trends."""
    ctx = context or build_member_context(user)
    return {
        "corporation_id": ctx.get("corporation_id"),
        "corporation_name": ctx.get("corporation_name", ""),
        "tribe_names": ctx.get("tribe_names", []),
        "prime_time": ctx.get("prime_time", ""),
        "tenure_days": ctx.get("tenure_days"),
        "tenure_cohort": ctx.get("tenure_cohort", ""),
        "activity_tier": ctx.get("activity_tier", ""),
        "role_flags": ctx.get("role_flags", []),
    }
