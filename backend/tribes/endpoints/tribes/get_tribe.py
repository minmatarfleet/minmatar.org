"""GET "/{tribe_id}" - tribe detail."""

from ninja import Router

from tribes.endpoints.groups.schemas import CharacterRefSchema
from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.models import Tribe, TribeGroupMembership


def _user_to_character_ref(user) -> "CharacterRefSchema | None":
    try:
        char = user.eveplayer.primary_character
        if char:
            return CharacterRefSchema(
                character_id=char.character_id,
                character_name=char.character_name,
            )
    except Exception:
        pass
    return None


PATH = "/{tribe_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Tribe detail.",
    "response": {200: TribeSchema, 404: dict},
}

router = Router(tags=["Tribes"])


def get_tribe(request, tribe_id: int):
    tribe = (
        Tribe.objects.filter(pk=tribe_id)
        .select_related("chief__eveplayer__primary_character")
        .first()
    )
    if not tribe:
        return 404, {"detail": "Tribe not found."}
    active_groups = tribe.groups.filter(is_active=True)
    total_members = (
        TribeGroupMembership.objects.filter(
            tribe_group__tribe=tribe,
            status=TribeGroupMembership.STATUS_APPROVED,
        )
        .values("user")
        .distinct()
        .count()
    )
    return 200, TribeSchema(
        id=tribe.pk,
        name=tribe.name,
        slug=tribe.slug,
        description=tribe.description,
        content=tribe.content,
        image_url=tribe.image_url,
        banner_url=tribe.banner_url,
        discord_channel_id=tribe.discord_channel_id,
        chief=_user_to_character_ref(tribe.chief) if tribe.chief else None,
        is_active=tribe.is_active,
        group_count=active_groups.count(),
        total_member_count=total_members,
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe)
