from datetime import timedelta

from celery.schedules import crontab, schedule

CELERYD_HIJACK_ROOT_LOGGER = False
# Queue/routing are set in app/celery.py so they apply for workers and producers.

# Retain broker connection retries on worker startup (Celery 6+)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Market
CELERYBEAT_MARKET = [
    (
        "[Market] Update Eve Universe Market Prices",
        {
            "task": "eveuniverse.tasks.update_market_prices",
            "schedule": crontab(minute=10, hour="*/2"),
        },
    ),
    (
        "[Market] Fetch Market Contracts",
        {
            "task": "market.tasks.fetch_eve_market_contracts",
            "schedule": schedule(timedelta(minutes=60)),
        },
    ),
    (
        "[Market] Fetch Structure Sell Orders",
        {
            "task": "market.tasks.fetch_structure_sell_orders",
            "schedule": crontab(minute=33, hour="*/4"),
        },
    ),
    (
        "[Market] Fetch Market Item History",
        {
            "task": "market.tasks.fetch_market_item_history",
            "schedule": crontab(minute=15, hour=12),
        },
    ),
    (
        "[Market] Low Stock Warnings",
        {
            "task": "market.tasks.notify_eve_market_contract_warnings",
            "schedule": crontab(minute=0, hour=14, day_of_week=1),
        },
    ),
    (
        "[Market] Update Moon Revenue",
        {
            "task": "moons.tasks.update_moon_revenues",
            "schedule": schedule(timedelta(hours=8)),
        },
    ),
]

# Characters (eveonline tasks use queue="eveonline" for admin "Run" and beat)
CELERYBEAT_CHARACTERS = [
    (
        "[Characters] Update Affiliations",
        {
            "task": "eveonline.tasks.affiliations.update_character_affilliations",
            "schedule": crontab(minute="0,30", hour="*"),
        },
    ),
    (
        "[Characters] Update Characters (assets, skills, killmails)",
        {
            "task": "eveonline.tasks.characters.update_alliance_characters",
            "schedule": crontab(minute=37, hour="*/4"),
            "options": {"queue": "eveonline"},
        },
    ),
    (
        "[Characters] Update Players",
        {
            "task": "eveonline.tasks.players.update_players",
            "schedule": schedule(timedelta(hours=8)),
        },
    ),
]

# Corporations (eveonline tasks use queue="eveonline" for admin "Run" and beat)
CELERYBEAT_CORPORATIONS = [
    (
        "[Corporations] Import Corporations",
        {
            "task": "eveonline.tasks.corporations.sync_alliance_corporations",
            "schedule": crontab(minute=0, hour="*/2"),
        },
    ),
    (
        "[Corporations] Update Corporations",
        {
            "task": "eveonline.tasks.corporations.update_corporations",
            "schedule": crontab(minute=0, hour="*/1"),
            "options": {"queue": "eveonline"},
        },
    ),
    (
        "[Corporations] Structure Notifications",
        {
            "task": "structures.tasks.process_structure_notifications",
            "schedule": crontab(minute="*", hour="*/1"),
        },
    ),
    (
        "[Corporations] Notify Low Fuel Structures",
        {
            "task": "structures.tasks.notify_low_fuel_structures",
            "schedule": crontab(minute=0, hour=12),
        },
    ),
    (
        "[Corporations] Update Structures",
        {
            "task": "structures.tasks.update_structures",
            "schedule": crontab(minute="19,49", hour="*"),
        },
    ),
]

# Industry (order assignees' jobs from ESI)
CELERYBEAT_INDUSTRY = [
    (
        "[Industry] Sync Jobs for Order Assignees",
        {
            "task": "industry.tasks.sync_industry_jobs_for_order_assignees",
            "schedule": crontab(minute=5, hour="*/4"),
        },
    ),
]

# Groups
CELERYBEAT_GROUPS = [
    (
        "[Groups] Remove Invalid Sig Members",
        {
            "task": "groups.tasks.remove_sigs",
            "schedule": schedule(timedelta(hours=1)),
        },
    ),
    (
        "[Groups] Remove Invalid Team Members",
        {
            "task": "groups.tasks.remove_teams",
            "schedule": schedule(timedelta(hours=1)),
        },
    ),
    (
        "[Groups] Sig Request Reminders",
        {
            "task": "groups.tasks.create_sig_request_reminders",
            "schedule": crontab(minute=0, hour=14, day_of_week=1),
        },
    ),
    (
        "[Groups] Sync Corporation Groups",
        {
            "task": "groups.tasks.sync_eve_corporation_groups",
            "schedule": crontab(minute="19,49", hour="*"),
        },
    ),
    (
        "[Groups] Team Request Reminders",
        {
            "task": "groups.tasks.create_team_request_reminders",
            "schedule": crontab(minute=0, hour=14, day_of_week=1),
        },
    ),
    (
        "[Groups] Update User Affiliations",
        {
            "task": "groups.tasks.update_affiliations",
            "schedule": crontab(minute="15,45", hour="*"),
        },
    ),
]

# Misc (Celery, Fleets, ESI, Reminders, Reddit, Discord, Mumble)
CELERYBEAT_OTHER = [
    (
        "[Misc] Backend Cleanup",
        {
            "task": "celery.backend_cleanup",
            "schedule": crontab(minute=0, hour=4),
            "options": {"expire_seconds": 43200},
        },
    ),
    (
        "[Misc] Check Fleets",
        {
            "task": "fleets.tasks.update_fleet_instances",
            "schedule": schedule(timedelta(seconds=30)),
        },
    ),
    (
        "[Misc] ESI Cleanup Callback Redirect",
        {
            "task": "esi.tasks.cleanup_callbackredirect",
            "schedule": crontab(minute=0, hour="*/4"),
        },
    ),
    (
        "[Misc] ESI Cleanup Token",
        {
            "task": "esi.tasks.cleanup_token",
            "schedule": crontab(minute=0, hour=0),
        },
    ),
    (
        "[Misc] Rat Quotes every day at downtime",
        {
            "task": "reminders.tasks.get_rat_quote",
            "schedule": crontab(minute=0, hour=13),
        },
    ),
    (
        "[Misc] Reddit scheduled post",
        {
            "task": "reddit.tasks.scheduled_reddit_posts",
            "schedule": crontab(minute=0, hour=13),
        },
    ),
    (
        "[Misc] Remove orphan discord user roles",
        {
            "task": "discord.tasks.remove_roles_from_unregistered_guild_members",
            "schedule": crontab(minute=0, hour=14, day_of_week=1),
        },
    ),
    (
        "[Misc] Set Mumble usernames",
        {
            "task": "mumble.tasks.set_mumble_usernames",
            "schedule": crontab(minute=0, hour=13),
        },
    ),
    (
        "[Misc] Sync Discord User Nicknames",
        {
            "task": "discord.tasks.sync_discord_user_nicknames",
            "schedule": crontab(minute="19,49", hour="*"),
        },
    ),
    (
        "[Misc] Sync Discord Users",
        {
            "task": "discord.tasks.sync_discord_users",
            "schedule": crontab(minute=0, hour=14, day_of_week=1),
        },
    ),
]

CELERYBEAT_SCHEDULE = dict(
    CELERYBEAT_MARKET
    + CELERYBEAT_CHARACTERS
    + CELERYBEAT_CORPORATIONS
    + CELERYBEAT_INDUSTRY
    + CELERYBEAT_GROUPS
    + CELERYBEAT_OTHER
)
