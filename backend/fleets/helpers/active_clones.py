"""Poll active fleet members for implant snapshots."""

import logging

from datetime import timedelta

from django.utils import timezone
from esi.models import Token

from eveonline.client import EsiClient
from eveonline.helpers.implants import build_slot_keyed_implants
from fleets.models import (
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberImplantSnapshot,
)
from market.helpers.pricing import get_prices_by_type_id

logger = logging.getLogger(__name__)

IMPLANT_SCOPE = ["esi-clones.read_implants.v1"]
POLL_SPREAD_SECONDS = 300
FLEET_POLL_WINDOW = timedelta(minutes=45)


def qualifying_fleet_instances():
    """Active fleet instances still within the 45-minute implant poll window."""
    cutoff = timezone.now() - FLEET_POLL_WINDOW
    return EveFleetInstance.objects.filter(
        end_time__isnull=True,
        start_time__gt=cutoff,
    )


def members_to_poll():
    """Members of qualifying fleet instances, in stable order."""
    fleet_instances = qualifying_fleet_instances()
    return list(
        EveFleetInstanceMember.objects.filter(
            eve_fleet_instance__in=fleet_instances
        ).order_by("id")
    )


def poll_fleet_member_implants(member_id: int) -> bool:
    """Poll one fleet member and append an implant snapshot row."""
    member = (
        EveFleetInstanceMember.objects.filter(pk=member_id)
        .select_related("eve_fleet_instance")
        .first()
    )
    if not member:
        logger.warning("Fleet member %s not found for implant poll", member_id)
        return False

    fleet_instance = member.eve_fleet_instance
    if fleet_instance.end_time is not None:
        return False
    if fleet_instance.start_time <= timezone.now() - FLEET_POLL_WINDOW:
        return False

    if not Token.get_token(member.character_id, IMPLANT_SCOPE):
        logger.debug(
            "No implant scope/token for fleet member %s (%s)",
            member.character_name,
            member.character_id,
        )
        return False

    response = EsiClient(member.character_id).get_character_implants()
    if not response.success():
        logger.warning(
            "Implant poll failed for %s (%s): %s",
            member.character_name,
            member.character_id,
            response.response_code,
        )
        return False

    type_ids = sorted({int(tid) for tid in (response.results() or [])})
    implants = build_slot_keyed_implants(type_ids)
    prices = get_prices_by_type_id(type_ids)
    estimated_value_isk = sum(prices.get(tid, 0) for tid in type_ids)

    EveFleetInstanceMemberImplantSnapshot.objects.create(
        member=member,
        implants=implants,
        estimated_value_isk=estimated_value_isk,
    )
    return True
