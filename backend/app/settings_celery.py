from datetime import timedelta

from celery.schedules import crontab, schedule

CELERYD_HIJACK_ROOT_LOGGER = False

CELERYBEAT_SCHEDULE = {
    "celery.backend_cleanup": {
        "task": "celery.backend_cleanup",
        "schedule": crontab(minute=0, hour=4),
        "options": {"expire_seconds": 43200},
    },
    "Check Fleets": {
        "task": "fleets.tasks.update_fleet_instances",
        "schedule": schedule(timedelta(seconds=30)),
    },
    "Delete orphaned assets": {
        "task": "eveonline.tasks.delete_orphan_assets",
        "schedule": crontab(minute=0, hour=13),
    },
    "esi_cleanup_callbackredirect": {
        "task": "esi.tasks.cleanup_callbackredirect",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "esi_cleanup_token": {
        "task": "esi.tasks.cleanup_token",
        "schedule": crontab(minute=0, hour=0),
    },
    "Fetch public contracts": {
        "task": "market.tasks.fetch_eve_public_contracts",
        "schedule": crontab(minute=21, hour="*/4"),
    },
    # "Find orphan assets": {
    #     "task": "eveonline.tasks.find_orphan_assets",
    #     "schedule": crontab(minute=0, hour=13),
    # },
    # "Fixup character tokens": {
    #     "task": "eveonline.tasks.fixup_character_tokens",
    #     "schedule": crontab(minute=0, hour=13),
    # },
    "Rat Quotes every day at downtime": {
        "task": "reminders.tasks.get_rat_quote",
        "schedule": crontab(minute=0, hour=13),
    },
    "Reddit scheduled post": {
        "task": "reddit.tasks.scheduled_reddit_posts",
        "schedule": crontab(minute=0, hour=13),
    },
    "Remove duplicate alliances": {
        "task": "eveonline.tasks.deduplicate_alliances",
        "schedule": crontab(minute=0, hour=14, day_of_week=1),
    },
    "Remove invalid member from sigs": {
        "task": "groups.tasks.remove_sigs",
        "schedule": schedule(timedelta(hours=1)),
    },
    "Remove invalid member from teams": {
        "task": "groups.tasks.remove_teams",
        "schedule": schedule(timedelta(hours=1)),
    },
    "Remove orphan discord user roles": {
        "task": "discord.tasks.remove_roles_from_unregistered_guild_members",
        "schedule": crontab(minute=0, hour=14, day_of_week=1),
    },
    "Send Sig Request Reminders": {
        "task": "groups.tasks.create_sig_request_reminders",
        "schedule": crontab(minute=0, hour=14, day_of_week=1),
    },
    "Send Team Request Reminders": {
        "task": "groups.tasks.create_team_request_reminders",
        "schedule": crontab(minute=0, hour=14, day_of_week=1),
    },
    "Set Mumble usernames": {
        "task": "mumble.tasks.set_mumble_usernames",
        "schedule": crontab(minute=0, hour=13),
    },
    # "Setup EvePlayer entities": {
    #     "task": "eveonline.tasks.setup_players",
    #     "schedule": crontab(minute=21, hour="*/4"),
    # },
    "Structure Notifications": {
        "task": "structures.tasks.process_structure_notifications",
        "schedule": crontab(minute="*", hour="*/1"),
    },
    "structures_notify_low_fuel": {
        "task": "structures.tasks.notify_low_fuel_structures",
        "schedule": crontab(minute=0, hour=12),
    },
    "Sync Corporation Groups": {
        "task": "groups.tasks.sync_eve_corporation_groups",
        "schedule": crontab(minute="19,49", hour="*"),
    },
    "Sync Discord User Nicknames": {
        "task": "discord.tasks.sync_discord_user_nicknames",
        "schedule": crontab(minute="19,49", hour="*"),
    },
    "Sync Discord Users": {
        "task": "discord.tasks.sync_discord_users",
        "schedule": crontab(minute=0, hour=14, day_of_week=1),
    },
    "Update Character Affiliations": {
        "task": "eveonline.tasks.update_character_affilliations",
        "schedule": crontab(minute="18,48", hour="*"),
    },
    "Update Character Assets": {
        "task": "eveonline.tasks.update_alliance_character_assets",
        "schedule": crontab(minute=37, hour="*/4"),
    },
    "Update Character Killmails": {
        "task": "eveonline.tasks.update_alliance_character_killmails",
        "schedule": crontab(minute=21, hour="*/4"),
    },
    "Update Character Skills": {
        "task": "eveonline.tasks.update_alliance_character_skills",
        "schedule": crontab(minute=21, hour="*/4"),
    },
    "Update Corporations": {
        "task": "eveonline.tasks.update_corporations",
        "schedule": crontab(minute=0, hour="*/1"),
    },
    "Update Courier Contracts": {
        "task": "freight.tasks.update_contracts",
        "schedule": crontab(minute="18,48", hour="*"),
    },
    "Update LP store items": {
        "task": "lpconversion.tasks.update_lpstore_items",
        "schedule": crontab(minute=0, hour=12),
    },
    "Update moon revenue": {
        "task": "moons.tasks.update_moon_revenues",
        "schedule": schedule(timedelta(hours=8)),
    },
    "Update players": {
        "task": "eveonline.tasks.update_players",
        "schedule": schedule(timedelta(hours=8)),
    },
    "Update Structures": {
        "task": "structures.tasks.update_structures",
        "schedule": crontab(minute="19,49", hour="*"),
    },
    "Update User Affiliations": {
        "task": "groups.tasks.update_affiliations",
        "schedule": crontab(minute="19,49", hour="*"),
    },
    "[Market] Low Stock Warnings": {
        "task": "market.tasks.notify_eve_market_contract_warnings",
        "schedule": crontab(minute=0, hour=14, day_of_week=1),
    },
    # "[Market] Update Contracts": {
    #     "task": "market.tasks.fetch_eve_market_contracts",
    #     "schedule": crontab(minute=21, hour="*/4"),
    # },
}
