"""PATCH "/groups/{group_id}/publishing" - change publishing settings."""

from django.db import transaction

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveCharacter
from tribes.endpoints.publishing.schemas import (
    TribeGroupPublishingPatch,
    TribeGroupPublishingSchema,
)
from tribes.endpoints.publishing.serializers import serialize_publishing
from tribes.helpers import user_can_manage_group
from tribes.helpers.discord_channels import channels_of_kind
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/groups/{group_id}/publishing"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Change who may publish as the group, and its channel.",
    "description": (
        "Managers of the group only. Every field is optional. Chosen "
        "publishers are given as character ids of active members."
    ),
    "response": {
        200: TribeGroupPublishingSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
}

KINDS = ("post", "fleet", "event")


def _publisher_users(group: TribeGroup, character_ids: list[int]):
    """Users for these characters, or an error for any that aren't active
    members of the group."""
    characters = EveCharacter.objects.filter(
        character_id__in=set(character_ids), user__isnull=False
    )
    user_ids = {c.character_id: c.user_id for c in characters}
    unknown = sorted(set(character_ids) - set(user_ids))
    if unknown:
        return 400, {"detail": f"Unknown characters: {unknown}"}
    members = set(
        TribeGroupMembership.objects.filter(
            tribe_group=group,
            user_id__in=set(user_ids.values()),
            status=TribeGroupMembership.STATUS_ACTIVE,
        ).values_list("user_id", flat=True)
    )
    outside = sorted(
        cid for cid, uid in user_ids.items() if uid not in members
    )
    if outside:
        return 400, {
            "detail": f"Not active members of {group.name}: {outside}"
        }
    return set(user_ids.values())


def _channel_error(channel_id: int | None):
    if channel_id is None:
        return None
    text = channels_of_kind("text")
    # Discord unreachable: trust the id rather than block the save.
    if text and channel_id not in {int(c["id"]) for c in text}:
        return 400, {"detail": f"{channel_id} is not a text channel"}
    return None


def _requested_publishers(group: TribeGroup, payload):
    """{kind: user ids} for the publisher lists sent, or an error."""
    publishers = {}
    for kind in KINDS:
        character_ids = getattr(payload, f"{kind}_publisher_character_ids")
        if character_ids is None:
            continue
        users = _publisher_users(group, character_ids)
        if isinstance(users, tuple):
            return users
        publishers[kind] = users
    return publishers


def _apply_settings(group: TribeGroup, payload) -> None:
    for kind in KINDS:
        policy = getattr(payload, f"{kind}_policy")
        if policy is not None:
            setattr(group, f"{kind}_policy", policy.value)
    for flag in ("allow_alliance_posts", "allow_open_fleets"):
        value = getattr(payload, flag)
        if value is not None:
            setattr(group, flag, value)
    if "discord_channel_id" in payload.model_fields_set:
        group.discord_channel_id = payload.discord_channel_id


def patch_group_publishing(
    request, group_id: int, payload: TribeGroupPublishingPatch
):
    group = (
        TribeGroup.objects.filter(pk=group_id)
        .select_related("tribe", "group__discord_group")
        .first()
    )
    if group is None:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, group):
        return 403, {"detail": "Only the group's managers can change this."}

    publishers = _requested_publishers(group, payload)
    if isinstance(publishers, tuple):
        return publishers
    if "discord_channel_id" in payload.model_fields_set:
        error = _channel_error(payload.discord_channel_id)
        if error:
            return error

    with transaction.atomic():
        _apply_settings(group, payload)
        group.save()
        for kind, user_ids in publishers.items():
            getattr(group, f"{kind}_publishers").set(user_ids)
    return 200, serialize_publishing(group)
