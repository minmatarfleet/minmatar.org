import { can_custom, feature_allows, legacy_superuser, type GateContext } from '@helpers/gates'

/** The fitting tags the editor offers (backend FittingTag). */
export const FITTING_TAG_SLUGS = [
    'highsec',
    'nullsec',
    'faction_warfare',
    'nanogang',
    'fleet_composition',
    'new_player_friendly',
    'capitals',
    'command_bursts',
    'industry',
    'escape_frigate',
] as const

/**
 * The fittings.doctrine.edit gate: the editor and the review queue. No site
 * editor existed before, so the legacy check is superuser or the pilot
 * feature. Whether a request can be approved is the API's call (`can_review`
 * on each request).
 */
export async function can_edit_doctrines(gates: GateContext): Promise<boolean> {
    return can_custom(gates, 'fittings.doctrine.edit', () =>
        legacy_superuser(gates) || feature_allows(gates, 'fittings.doctrine.edit')
    )
}
