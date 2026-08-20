"""Build the give-back card shown to a member on submission: their own quarter
next to the community's. All values come from cached platform data."""

import logging

from alliance.models import AllianceHealthSnapshot
from eveonline.models import EveCharacterSkillset
from learning.helpers import completed_learning_ids
from srp.models import EveFleetShipReimbursement
from surveys.helpers.autofill import _character_ids, fleets_attended
from surveys.helpers.tenure import quarter_window

logger = logging.getLogger(__name__)


def _srp_received(user) -> dict:
    try:
        qs = EveFleetShipReimbursement.objects.filter(user=user)
        approved = qs.filter(status="approved")
        total = sum(a.amount or 0 for a in approved)
        return {"count": approved.count(), "isk": total}
    except Exception:  # pragma: no cover - defensive
        return {"count": 0, "isk": 0}


def _guides_completed(user) -> int:
    try:
        return len(list(completed_learning_ids(user)))
    except Exception:  # pragma: no cover - defensive
        return 0


def _doctrines_ready(user) -> int:
    """Skillsets the member fully meets (progress complete)."""
    try:
        char_ids = _character_ids(user)
        return (
            EveCharacterSkillset.objects.filter(
                character__character_id__in=char_ids, progress__gte=1.0
            )
            .values("eve_skillset")
            .distinct()
            .count()
        )
    except Exception:  # pragma: no cover - defensive
        return 0


def _primary_tribe(user) -> str:
    try:
        m = (
            user.tribe_memberships.filter(status="active")
            .select_related("tribe_group__tribe")
            .first()
        )
        if m and m.tribe_group:
            return m.tribe_group.name
    except Exception:  # pragma: no cover - defensive
        pass
    return "—"


def _community_snapshot() -> dict:
    """Best-effort community figures from stored health/activity data."""
    active_pilots = None
    try:
        latest = AllianceHealthSnapshot.objects.order_by("-created_at").first()
        if latest is not None:
            active_pilots = getattr(latest, "active_pilots", None) or getattr(
                latest, "total_active", None
            )
    except Exception:  # pragma: no cover - defensive
        active_pilots = None
    return {"active_pilots": active_pilots}


def build_giveback_card(user, campaign=None) -> dict:
    start, end = quarter_window()
    srp = _srp_received(user)
    personal = {
        "fleets_flown": fleets_attended(user, start, end),
        "doctrines_ready": _doctrines_ready(user),
        "guides_completed": _guides_completed(user),
        "srp_count": srp["count"],
        "srp_isk": srp["isk"],
        "tribe": _primary_tribe(user),
    }
    return {"personal": personal, "community": _community_snapshot()}
