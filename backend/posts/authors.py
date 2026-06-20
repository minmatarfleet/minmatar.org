from django.contrib.auth.models import User

from eveonline.helpers.characters import user_primary_character

MINMATAR_FLEET_AUTHOR_NAME = "Minmatar Fleet"


def post_author_fields(user: User) -> tuple[int, str]:
    primary = user_primary_character(user)
    if primary:
        return primary.character_id, primary.character_name
    return 0, MINMATAR_FLEET_AUTHOR_NAME
