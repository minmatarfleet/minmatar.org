# Character helpers. Re-export for backward compatibility:
#   from eveonline.helpers.characters import user_primary_character
from eveonline.helpers.characters.affiliations import (
    update_character_with_affiliations,
)
from eveonline.helpers.characters.assets import (
    create_character_assets,
    non_ship_location,
)
from eveonline.helpers.characters.characters import (
    character_desired_scopes,
    character_primary,
    player_characters,
    related_characters,
    set_primary_character,
    user_characters,
    user_player,
    user_primary_character,
)
from eveonline.helpers.characters.skills import (
    compare_skills_to_skillset,
    create_eve_character_skillset,
    upsert_character_skill,
    upsert_character_skills,
)
from eveonline.helpers.characters.update import (
    update_character_assets,
    update_character_killmails,
    update_character_skills,
)

__all__ = [
    "character_desired_scopes",
    "character_primary",
    "create_character_assets",
    "create_eve_character_skillset",
    "compare_skills_to_skillset",
    "non_ship_location",
    "related_characters",
    "set_primary_character",
    "update_character_assets",
    "update_character_killmails",
    "update_character_skills",
    "update_character_with_affiliations",
    "user_characters",
    "user_player",
    "user_primary_character",
    "upsert_character_skill",
    "upsert_character_skills",
]
