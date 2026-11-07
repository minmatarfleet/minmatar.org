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

/** Doctrine roles in display order. The stored key "secondary" is Academy. */
export const DOCTRINE_ROLES = ['primary', 'secondary', 'support', 'utility', 'capitals'] as const
export type DoctrineRole = typeof DOCTRINE_ROLES[number]
export type DoctrineComposition = Record<DoctrineRole, number[]>

export const is_doctrine_role = (value:string):value is DoctrineRole =>
    (DOCTRINE_ROLES as readonly string[]).includes(value)

export interface CompositionChange {
    fitting_id: number
    kind:       'added' | 'moved' | 'removed'
    from:       DoctrineRole | null
    to:         DoctrineRole | null
}

/**
 * One row per fitting whose roles changed: added, moved (one role to
 * another) or removed. A fitting in several roles gets one row per role it
 * gained or lost. Added rows come first, then moved, then removed.
 */
export function composition_changes(current:DoctrineComposition, proposed:DoctrineComposition):CompositionChange[] {
    const roles_of = (composition:DoctrineComposition, id:number) =>
        DOCTRINE_ROLES.filter((role) => (composition[role] ?? []).includes(id))
    const ids = new Set<number>()
    for (const role of DOCTRINE_ROLES)
        for (const id of [...(current[role] ?? []), ...(proposed[role] ?? [])]) ids.add(id)

    const changes:CompositionChange[] = []
    for (const id of ids) {
        const before = roles_of(current, id)
        const after = roles_of(proposed, id)
        const gained = after.filter((role) => !before.includes(role))
        const lost = before.filter((role) => !after.includes(role))
        if (gained.length === 1 && lost.length === 1) {
            changes.push({ fitting_id: id, kind: 'moved', from: lost[0], to: gained[0] })
            continue
        }
        for (const role of gained) changes.push({ fitting_id: id, kind: 'added', from: null, to: role })
        for (const role of lost) changes.push({ fitting_id: id, kind: 'removed', from: role, to: null })
    }
    const order = { added: 0, moved: 1, removed: 2 }
    return changes.sort((a, b) => order[a.kind] - order[b.kind])
}

/** Hull-class filters the editor's search offers, by SDE ship group. */
export const HULL_FILTERS = ['capitals', 'logistics', 'recon'] as const
export type HullFilter = typeof HULL_FILTERS[number]

const LOGISTICS_GROUPS = ['Logistics', 'Logistics Frigate', 'Force Auxiliary']
const RECON_GROUPS = ['Force Recon Ship', 'Combat Recon Ship']

export function hull_filters_for(group:string | null | undefined, is_capital:(group:string) => boolean):HullFilter[] {
    if (!group) return []
    const filters:HullFilter[] = []
    if (is_capital(group)) filters.push('capitals')
    if (LOGISTICS_GROUPS.includes(group)) filters.push('logistics')
    if (RECON_GROUPS.includes(group)) filters.push('recon')
    return filters
}

/** A fitting as the editor lists it: hull line, search text, hull filters. */
export interface EditorFitting {
    id:      number
    name:    string
    ship_id: number
    hull:    string
    search:  string
    filters: string
}

export function editor_fitting(
    fitting:{ id:number, name:string, ship_id:number },
    hull_name:string | undefined,
    group:string | undefined,
    is_capital:(group:string) => boolean,
):EditorFitting {
    const hull = [hull_name, group].filter(Boolean).join(' · ')
    return {
        id: fitting.id,
        name: fitting.name,
        ship_id: fitting.ship_id,
        hull,
        search: `${fitting.name} ${hull}`.toLowerCase(),
        filters: hull_filters_for(group, is_capital).join(' '),
    }
}

/** Text placed inside a single-quoted string in an Alpine expression. */
export const alpine_string = (text:string) => text.replace(/\\/g, '\\\\').replace(/'/g, "\\'")

export const ship_icon = (ship_id:number) => `https://images.evetech.net/types/${ship_id}/icon?size=64`
