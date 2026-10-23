from django.db.models import Count

from eveonline.helpers.characters.characters import user_primary_character
from notifications.models import NotificationChannel, NotificationDelivery
from notifications.types.tribes import TRIBE_INVITED_KEY
from tribes.helpers.invitations import effective_status, invited_delivery_key
from tribes.models import TribeGroupMembershipCharacter


def _iso(value):
    return value.isoformat() if value else None


def _dm_deliveries(invitations) -> dict[str, NotificationDelivery]:
    keys = [f"{invited_delivery_key(i)}:u{i.user_id}" for i in invitations]
    if not keys:
        return {}
    return {
        d.idempotency_key: d
        for d in NotificationDelivery.objects.filter(
            notification_type=TRIBE_INVITED_KEY,
            channel=NotificationChannel.DISCORD,
            idempotency_key__in=keys,
        )
    }


def serialize_invitations(invitations) -> list[dict]:
    """Serialize invites with their pilots, inviters and DM state."""
    invitations = list(invitations)
    deliveries = _dm_deliveries(invitations)
    membership_ids = [i.membership_id for i in invitations if i.membership_id]
    joined_counts = dict(
        TribeGroupMembershipCharacter.objects.filter(
            membership_id__in=membership_ids
        )
        .values("membership_id")
        .annotate(n=Count("id"))
        .values_list("membership_id", "n")
    )
    primaries = {}
    rows = []
    for invitation in invitations:
        for user in (invitation.user, invitation.invited_by):
            if user is not None and user.pk not in primaries:
                primaries[user.pk] = user_primary_character(user)
        pilot = primaries.get(invitation.user_id)
        inviter = (
            primaries.get(invitation.invited_by_id)
            if invitation.invited_by_id
            else None
        )
        delivery = deliveries.get(
            f"{invited_delivery_key(invitation)}:u{invitation.user_id}"
        )
        tribe_group = invitation.tribe_group
        rows.append(
            {
                "id": invitation.pk,
                "tribe_id": tribe_group.tribe_id,
                "tribe_name": tribe_group.tribe.name,
                "tribe_group_id": tribe_group.pk,
                "tribe_group_name": tribe_group.name,
                "user_id": invitation.user_id,
                "character_id": pilot.character_id if pilot else None,
                "character_name": (
                    pilot.character_name if pilot else invitation.user.username
                ),
                "invited_by_id": invitation.invited_by_id,
                "invited_by_character_id": (
                    inviter.character_id if inviter else None
                ),
                "invited_by_name": (
                    inviter.character_name
                    if inviter
                    else (
                        invitation.invited_by.username
                        if invitation.invited_by
                        else ""
                    )
                ),
                "note": invitation.note,
                "status": effective_status(invitation),
                "created_at": _iso(invitation.created_at),
                "expires_at": _iso(invitation.expires_at),
                "responded_at": _iso(invitation.responded_at),
                "joined_character_count": joined_counts.get(
                    invitation.membership_id
                ),
                "dm_status": delivery.status if delivery else None,
                "dm_error": (delivery.error or "") if delivery else "",
            }
        )
    return rows


def serialize_invitation(invitation) -> dict:
    return serialize_invitations([invitation])[0]
