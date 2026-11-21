import type { StructureLocationCard } from '@dtypes/api.minmatar.org'

export type StructureView = 'all' | 'staging' | 'production' | 'reactions' | 'reprocessing' | 'freight' | 'market'
export const STRUCTURE_VIEWS: StructureView[] = ['all', 'staging', 'production', 'reactions', 'reprocessing', 'freight', 'market']

/** Old `?view=` values that still open the closest view (links pasted in Discord). */
const VIEW_ALIASES: Record<string, StructureView> = {
    industry: 'production',
    logistics: 'freight',
}

export function parse_structure_view(requested: string | null): StructureView {
    const name = requested ?? 'all'
    if ((STRUCTURE_VIEWS as string[]).includes(name)) return name as StructureView
    return VIEW_ALIASES[name] ?? 'all'
}

export type StructureFlag = 'home' | 'deployment' | 'fleets' | 'freight' | 'market' | 'orders'

/** Status tags the site derives from EveLocation and open orders. Browse
 * cards show Home and Deployment as a banner instead, so they ask for the
 * tags without them (`banner: false`). */
export function structure_flags(
    card: Pick<StructureLocationCard, 'staging' | 'deployment' | 'fleets' | 'freight' | 'market' | 'industry_orders'>,
    { banner = true }: { banner?: boolean } = {},
) {
    const flags: { kind: StructureFlag, count?: number }[] = []
    if (banner && card.staging) flags.push({ kind: 'home' })
    if (banner && card.deployment) flags.push({ kind: 'deployment' })
    if (card.fleets) flags.push({ kind: 'fleets' })
    if (card.freight) flags.push({ kind: 'freight' })
    if (card.market) flags.push({ kind: 'market' })
    if (card.industry_orders > 0) flags.push({ kind: 'orders', count: card.industry_orders })
    return flags
}

export type StructureBanner = 'home' | 'deployment'

/** The big banner on a card: the home staging, or a deployment staging. */
export function structure_banner(card: Pick<StructureLocationCard, 'staging' | 'deployment'>): StructureBanner | null {
    if (card.staging) return 'home'
    if (card.deployment) return 'deployment'
    return null
}

/** Rigs filter groups, in menu order, under their section. The keys match
 * `RIG_GROUPS` in backend/structures/locations.py. */
export const RIG_GROUP_SECTIONS = [
    { section: 'manufacturing', groups: ['capital_production', 'subcap_production', 'module_production', 'ammo_production', 'drone_production', 'component_production'] },
    { section: 'reactions', groups: ['composite_reactions', 'biochemical_reactions', 'hybrid_reactions'] },
    { section: 'science', groups: ['research', 'invention'] },
    { section: 'processing', groups: ['reprocessing', 'grading'] },
] as const

export type RigGroup = typeof RIG_GROUP_SECTIONS[number]['groups'][number]
export const RIG_GROUPS: RigGroup[] = RIG_GROUP_SECTIONS.flatMap((section) => [...section.groups])

/** `?rigs=a,b` (or repeated `?rigs=`) → the known groups, in menu order. */
export function parse_rig_groups(requested: string[]): RigGroup[] {
    const asked = new Set(requested.flatMap((value) => value.split(',')).map((value) => value.trim()))
    return RIG_GROUPS.filter((group) => asked.has(group))
}

export function rig_groups_of(card: Pick<StructureLocationCard, 'rigs'>): Set<string> {
    return new Set(card.rigs.map((rig) => rig.group).filter(Boolean))
}

/** A card matches the Rigs filter when it has any of the picked groups. */
export function has_rig_group(card: Pick<StructureLocationCard, 'rigs'>, groups: RigGroup[]) {
    if (groups.length === 0) return true
    const own = rig_groups_of(card)
    return groups.some((group) => own.has(group))
}

const PRODUCTION_GROUPS = new Set<string>(RIG_GROUP_SECTIONS[0].groups)
const REACTION_GROUPS = new Set<string>(RIG_GROUP_SECTIONS[1].groups)
const PROCESSING_GROUPS = new Set<string>(RIG_GROUP_SECTIONS[3].groups)

function has_service(card: Pick<StructureLocationCard, 'services'>, words: string) {
    return card.services.some((service) => service.includes(words))
}

function has_any(own: Set<string>, groups: Set<string>) {
    return [...own].some((group) => groups.has(group))
}

/** Which locations each browse view shows. */
export function in_view(card: StructureLocationCard, view: StructureView) {
    switch (view) {
        case 'staging': return card.staging || card.deployment
        // An unscanned structure someone tagged "industry" stays under Production.
        case 'production': return has_service(card, 'Manufacturing') || has_any(rig_groups_of(card), PRODUCTION_GROUPS)
            || (card.good_for.includes('industry') && card.rigs.length === 0 && card.services.length === 0)
        case 'reactions': return has_service(card, 'Reactor') || has_any(rig_groups_of(card), REACTION_GROUPS)
        case 'reprocessing': return has_service(card, 'Reprocessing') || has_any(rig_groups_of(card), PROCESSING_GROUPS)
        case 'freight': return card.good_for.includes('logistics') || card.freight || card.route_count > 0
        case 'market': return card.market
        default: return true
    }
}

/** CSS colour token for a system's security status, as EVE colours it. */
export function security_colour(security: number | null | undefined) {
    if (security === null || security === undefined) return 'var(--text-muted)'
    if (security >= 0.95) return 'var(--security-status-1)'
    if (security <= 0) return 'var(--security-status-null)'
    const step = Math.max(1, Math.min(9, Math.round(security * 10)))
    return `var(--security-status-point-${step})`
}

export function security_label(security: number | null | undefined) {
    if (security === null || security === undefined) return ''
    return (Math.round(security * 10) / 10).toFixed(1)
}
