"""Live display context for the Content section: recent fleets and the FCs who
ran them, per content bracket, so members rate on the full quarter rather than
just the last thing they remember. Read-only, cached-DB, fully guarded.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from fleets.models import EveFleet
from learning.models import Learning

logger = logging.getLogger(__name__)

# Survey bracket key → EveFleet.type value.
BRACKET_TO_TYPE = {
    "strategic": "strategic",
    "non_strategic": "non_strategic",
    "training": "training",
}


def _pc(user) -> tuple[int | None, str]:
    if not user:
        return None, ""
    try:
        player = getattr(user, "eveplayer", None)
        pc = player.primary_character if player else None
        if pc:
            return pc.character_id, pc.character_name
    except Exception:  # pragma: no cover - defensive
        pass
    return None, getattr(user, "username", "") or ""


def _fleet_title(fleet) -> str:
    try:
        if fleet.doctrine_id and fleet.doctrine:
            return fleet.doctrine.name
        if fleet.audience_id and fleet.audience:
            return fleet.audience.name
        if fleet.description:
            return fleet.description.strip().splitlines()[0][:60]
    except Exception:  # pragma: no cover - defensive
        pass
    return "Fleet"


def _training_resources() -> list[dict]:
    try:
        return [
            {"title": item.title, "url": item.url}
            for item in Learning.objects.all().order_by("order")[:4]
        ]
    except Exception:  # pragma: no cover - defensive
        return []


def content_bracket_context(bracket: str) -> dict:
    fleet_type = BRACKET_TO_TYPE.get(bracket)
    recent_fleets: list[dict] = []
    fcs: list[dict] = []
    if fleet_type:
        try:
            window = timezone.now() - timedelta(days=90)
            qs = (
                EveFleet.objects.filter(
                    type=fleet_type, start_time__gte=window
                )
                .select_related(
                    "created_by__eveplayer__primary_character",
                    "audience",
                    "doctrine",
                )
                .order_by("-start_time")
            )
            seen_fc = set()
            for fleet in qs[:40]:
                fc_id, fc_name = _pc(fleet.created_by)
                if len(recent_fleets) < 5:
                    recent_fleets.append(
                        {
                            "title": _fleet_title(fleet),
                            "date": (
                                fleet.start_time.date().isoformat()
                                if fleet.start_time
                                else ""
                            ),
                            "fc_id": fc_id,
                            "fc_name": fc_name,
                            "objective": (fleet.description or "").strip(),
                        }
                    )
                uid = fleet.created_by_id
                if uid and uid not in seen_fc:
                    seen_fc.add(uid)
                    if fc_id:
                        fcs.append(
                            {"character_id": fc_id, "character_name": fc_name}
                        )
        except Exception:  # pragma: no cover - defensive
            logger.debug(
                "content context failed for %s", bracket, exc_info=True
            )

    context = {"fcs": fcs, "recent_fleets": recent_fleets, "resources": []}
    if bracket == "training":
        context["resources"] = _training_resources()
    return context


def resolve_context(context_source: str) -> dict | None:
    if context_source.startswith("content:"):
        return content_bracket_context(context_source.split(":", 1)[1])
    return None
