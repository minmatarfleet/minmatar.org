"""Who may connect a tribe's Discord and map its roles."""

from tribes.helpers.permissions import user_is_tribe_chief
from tribes.models import Tribe


def load_tribe(tribe_id: int) -> Tribe | None:
    return Tribe.objects.filter(pk=tribe_id).first()


def can_manage_tribe_discord(user, tribe: Tribe) -> bool:
    """The chief, including an interim executor."""
    if not getattr(user, "is_authenticated", False) or not getattr(
        user, "pk", None
    ):
        return False
    return user_is_tribe_chief(user, tribe)
