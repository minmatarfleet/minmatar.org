"""GET /affiliations/members - our pilots who keep flying with a bloc."""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Max, Sum

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.helpers.characters.identity import (
    primary_characters_for_characters,
)
from eveonline.models import EveCharacter
from intel.affiliations import resolve
from intel.affiliations.constants import ASSOCIATE_MONTHS, ASSOCIATE_SHARED
from intel.affiliations.score import window
from intel.endpoints.affiliations.common import FORBIDDEN, can_manage, endpoint
from intel.endpoints.affiliations.schemas import MemberCrosscheckResponse
from intel.models import IntelCoAttack


@endpoint(
    "get",
    "/members",
    summary="Our pilots who keep turning up on another bloc's kills",
    description=(
        "Characters registered on this site that were on an investigated "
        "group's sampled kills as often as an associate would be. Leads "
        "for a conversation, not proof: a merc contract or a third party "
        "on the same brawl looks the same."
    ),
    auth=AuthBearer(),
    response={200: MemberCrosscheckResponse, 403: ErrorResponse},
)
def get_member_crosscheck(request):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    ours = dict(
        EveCharacter.objects.values_list("character_id", "character_name")
    )
    blocs = resolve.bloc_map()
    rows = (
        IntelCoAttack.objects.filter(
            partner_kind="character",
            partner_id__in=list(ours),
            month__in=window(),
            shared__gt=0,
        )
        .values("partner_id", "entity__kind", "entity__eve_id", "entity__name")
        .annotate(
            # Flying together for the same militia is just FW.
            shared=Sum("shared") - Sum("militia_shared"),
            months=Count("month", distinct=True),
            last=Max("month"),
        )
    )
    our_bloc = resolve.bloc_for_group(
        "alliance", MINMATAR_FLEET_ALLIANCE_ID, blocs=blocs
    )
    by_bloc: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"shared": 0, "months": 0, "last": None, "groups": []}
    )
    for row in rows:
        bloc = resolve.bloc_for_group(
            row["entity__kind"], row["entity__eve_id"], blocs=blocs
        )
        if bloc is None or row["shared"] <= 0:
            continue
        if our_bloc and bloc["id"] == our_bloc["id"]:
            continue
        entry = by_bloc[(row["partner_id"], bloc["id"])]
        entry["bloc"] = resolve.public_entry(bloc)
        entry["shared"] += row["shared"]
        entry["months"] = max(entry["months"], row["months"])
        entry["last"] = max(filter(None, [entry["last"], row["last"]]))
        entry["groups"].append(
            {
                "kind": row["entity__kind"],
                "id": row["entity__eve_id"],
                "name": row["entity__name"] or str(row["entity__eve_id"]),
            }
        )
    flagged = {
        key: entry
        for key, entry in by_bloc.items()
        if entry["shared"] >= ASSOCIATE_SHARED
        and entry["months"] >= ASSOCIATE_MONTHS
    }
    mains = primary_characters_for_characters(
        list({character_id for character_id, _ in flagged})
    )
    members = [
        {
            "character_id": character_id,
            "character_name": ours.get(character_id, str(character_id)),
            "main_character_name": (
                mains[character_id].character_name
                if mains.get(character_id)
                else None
            ),
            "bloc": entry["bloc"],
            "shared": entry["shared"],
            "months_together": entry["months"],
            "last_month": entry["last"],
            "groups": entry["groups"],
        }
        for (character_id, _), entry in flagged.items()
    ]
    members.sort(key=lambda m: (-m["shared"], m["character_name"]))
    return MemberCrosscheckResponse(members=members)
