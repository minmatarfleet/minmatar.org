from tribes.endpoints.chief_volunteers.schemas import ChiefVolunteerSchema
from tribes.helpers.chiefs import seat_name
from tribes.models import TribeChiefVolunteer


def serialize_volunteer(offer: TribeChiefVolunteer) -> ChiefVolunteerSchema:
    player = getattr(offer.user, "eveplayer", None)
    primary = getattr(player, "primary_character", None) if player else None
    return ChiefVolunteerSchema(
        id=offer.pk,
        tribe_id=offer.tribe_id,
        tribe_name=offer.tribe.name,
        tribe_group_id=offer.tribe_group_id,
        seat_name=seat_name(offer),
        user_id=offer.user_id,
        character_id=primary.character_id if primary else None,
        character_name=(
            primary.character_name if primary else offer.user.username
        ),
        note=offer.note,
        status=offer.status,
        created_at=offer.created_at.isoformat(),
        decided_at=offer.decided_at.isoformat() if offer.decided_at else None,
    )
