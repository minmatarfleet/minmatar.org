BASIC_SCOPES = [
    "esi-corporations.read_structures.v1",
    "esi-fleets.read_fleet.v1",
    "esi-fleets.write_fleet.v1",
    "esi-assets.read_assets.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-characters.read_loyalty.v1",
    "esi-killmails.read_killmails.v1",
    "esi-characters.read_fw_stats.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
]

ADVANCED_SCOPES = [
    "esi-characters.read_blueprints.v1",
    "esi-planets.manage_planets.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
] + BASIC_SCOPES

CEO_SCOPES = [
    "esi-corporations.read_corporation_membership.v1",
    "esi-corporations.read_blueprints.v1",
    "esi-corporations.read_contacts.v1",
    "esi-corporations.read_container_logs.v1",
    "esi-corporations.read_divisions.v1",
    "esi-corporations.read_facilities.v1",
    "esi-corporations.read_fw_stats.v1",
    "esi-corporations.read_medals.v1",
    "esi-corporations.read_starbases.v1",
    "esi-corporations.read_titles.v1",
    "esi-wallet.read_corporation_wallets.v1",
] + ADVANCED_SCOPES

# Used for the freight CEO (Minmatar Fleet Logistics)
FREIGHT_CHARACTER_SCOPES = [
    "esi-contracts.read_corporation_contracts.v1"
] + CEO_SCOPES

# Used for supply team seeders (characters, build corporations)
MARKET_CHARACTER_SCOPES = [
    "esi-wallet.read_character_wallet.v1",
    "esi-markets.read_corporation_orders.v1",
    "esi-markets.read_character_orders.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-contracts.read_corporation_contracts.v1",
] + CEO_SCOPES

EXECUTOR_CHARACTER_SCOPES = [
    "esi-mail.send_mail.v1",
] + CEO_SCOPES
