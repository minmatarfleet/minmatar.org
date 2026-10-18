from django.contrib.auth.models import User

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter

MINMATAR_FLEET_AUTHOR_NAME = "Minmatar Fleet"


def post_author_fields(user: User) -> tuple[int, str]:
    return author_fields_for_main(user_primary_character(user))


def author_fields_for_main(primary: EveCharacter | None) -> tuple[int, str]:
    if primary:
        return primary.character_id, primary.character_name
    return 0, MINMATAR_FLEET_AUTHOR_NAME
