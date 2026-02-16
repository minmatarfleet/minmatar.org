"""
Eveonline Celery tasks package.

Import all task modules so Celery autodiscover_tasks() registers every task
when it loads eveonline.tasks. Also re-export task functions for callers that
do `from eveonline.tasks import update_character`, etc.
"""

from eveonline.tasks import affiliations, characters, corporations, players

task_config = affiliations.task_config

__all__ = [
    "task_config",
    "update_character_affilliations",
    "update_character",
    "update_alliance_characters",
    "fixup_character_tokens",
    "update_corporations",
    "sync_alliance_corporations",
    "update_corporation",
    "setup_players",
    "update_players",
]

update_character_affilliations = affiliations.update_character_affilliations
update_character = characters.update_character
update_alliance_characters = characters.update_alliance_characters
fixup_character_tokens = players.fixup_character_tokens

update_corporations = corporations.update_corporations
sync_alliance_corporations = corporations.sync_alliance_corporations
update_corporation = corporations.update_corporation

setup_players = players.setup_players
update_players = players.update_players
