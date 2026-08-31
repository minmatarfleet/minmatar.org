/** Mirrors backend/eveonline/scopes.py for UI tooltips. */

const BASIC_SCOPES = [
    'esi-corporations.read_structures.v1',
    'esi-fleets.read_fleet.v1',
    'esi-fleets.write_fleet.v1',
    'esi-assets.read_assets.v1',
    'esi-skills.read_skills.v1',
    'esi-skills.read_skillqueue.v1',
    'esi-characters.read_loyalty.v1',
    'esi-killmails.read_killmails.v1',
    'esi-characters.read_fw_stats.v1',
    'esi-clones.read_clones.v1',
    'esi-clones.read_implants.v1',
] as const

const DIRECTOR_SCOPES = [
    'esi-characters.read_notifications.v1',
    'esi-corporations.read_corporation_membership.v1',
    'esi-corporations.read_blueprints.v1',
    'esi-corporations.read_contacts.v1',
    'esi-corporations.read_container_logs.v1',
    'esi-corporations.read_divisions.v1',
    'esi-corporations.read_facilities.v1',
    'esi-corporations.read_fw_stats.v1',
    'esi-corporations.read_medals.v1',
    'esi-corporations.read_standings.v1',
    'esi-corporations.read_starbases.v1',
    'esi-corporations.read_titles.v1',
    'esi-corporations.track_members.v1',
    'esi-assets.read_corporation_assets.v1',
    'esi-killmails.read_corporation_killmails.v1',
    'esi-planets.read_customs_offices.v1',
    'esi-wallet.read_corporation_wallets.v1',
] as const

const INDUSTRY_SCOPES = [
    'esi-characters.read_blueprints.v1',
    'esi-characters.read_agents_research.v1',
    'esi-planets.manage_planets.v1',
    'esi-planets.read_customs_offices.v1',
    'esi-industry.read_character_jobs.v1',
    'esi-industry.read_character_mining.v1',
    'esi-industry.read_corporation_jobs.v1',
    'esi-industry.read_corporation_mining.v1',
] as const

const MARKET_SCOPES = [
    'esi-wallet.read_character_wallet.v1',
    'esi-wallet.read_corporation_wallets.v1',
    'esi-contracts.read_character_contracts.v1',
    'esi-contracts.read_corporation_contracts.v1',
    'esi-markets.read_character_orders.v1',
    'esi-markets.read_corporation_orders.v1',
    'esi-markets.structure_markets.v1',
] as const

const EXECUTOR_SCOPES = [
    'esi-mail.send_mail.v1',
    'esi-access.read_lists.v1',
] as const

const TOKEN_SCOPES: Record<string, readonly string[]> = {
    Basic: BASIC_SCOPES,
    Director: [...BASIC_SCOPES, ...DIRECTOR_SCOPES],
    Industry: [...BASIC_SCOPES, ...INDUSTRY_SCOPES],
    Market: [...BASIC_SCOPES, ...DIRECTOR_SCOPES, ...MARKET_SCOPES],
    Executor: [
        ...BASIC_SCOPES,
        ...DIRECTOR_SCOPES,
        ...MARKET_SCOPES,
        ...EXECUTOR_SCOPES,
    ],
    Public: ['publicData'],
}

/**
 * Scopes required by `token_type` that are beyond the standard Basic set.
 * Empty when the type is Basic/unknown or has no elevated scopes.
 */
export function elevated_scopes_for_token_type(
    token_type: string | null | undefined,
): string[] {
    const key = (token_type ?? '').trim()
    if (!key || key === 'Basic') return []

    const scopes = TOKEN_SCOPES[key]
    if (!scopes) return []

    const basic = new Set<string>(BASIC_SCOPES)
    return scopes.filter((scope) => !basic.has(scope))
}
