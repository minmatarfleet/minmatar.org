"""POST "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/approve"."""

import logging

from django.utils import timezone
from ninja import Router

from authentication import AuthBearer
from discord.client import DiscordClient
from tribes.endpoints.memberships.schemas import MembershipSchema
from tribes.endpoints.memberships.serializers import serialize_membership
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership

logger = logging.getLogger(__name__)

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/approve"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Approve a pending membership (chief only).",
    "response": {200: MembershipSchema, 400: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Memberships"])


def post_membership_approve(
    request, tribe_id: int, group_id: int, membership_id: int
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {
            "detail": "You do not have permission to approve memberships here."
        }

    membership = TribeGroupMembership.objects.filter(
        pk=membership_id, tribe_group=tg
    ).first()
    if not membership:
        return 404, {"detail": "Membership not found."}
    if membership.status != TribeGroupMembership.STATUS_PENDING:
        return 400, {
            "detail": f"Cannot approve a membership with status '{membership.status}'."
        }

    membership.status = TribeGroupMembership.STATUS_ACTIVE
    membership.approved_by = request.user
    membership.approved_at = timezone.now()
    membership.history_changed_by = request.user
    membership.save()

    membership = (
        TribeGroupMembership.objects.select_related(
            "user__eveplayer__primary_character",
        )
        .prefetch_related("characters__character")
        .get(pk=membership.pk)
    )
    return 200, serialize_membership(
        membership,
        include_requirement_status=True,
        include_characters=True,
    )


def _send_welcome_message(user, tg):
    """Post a welcome message tagging the new member in the tribe channel."""
    channel_id = tg.discord_channel_id or tg.tribe.discord_channel_id
    if not channel_id:
        return
    try:
        discord_user = getattr(user, "discord_user", None)
        mention = f"<@{discord_user.id}>" if discord_user else user.username
        DiscordClient().create_message(
            channel_id,
            message=f"Welcome {mention} to **{tg.name}**! o7",
        )
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Failed to send welcome message for user %s joining group %s",
            user,
            tg,
            exc_info=True,
        )


router.post(PATH, **ROUTE_SPEC)(post_membership_approve)
