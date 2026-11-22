import type { StructureLocationCard, StructureLocationModule } from '@dtypes/api.minmatar.org'
import { get_item_icon } from '@helpers/eve_image'

export type StructureView = 'all' | 'staging' | 'production' | 'reactions' | 'reprocessing'
export const STRUCTURE_VIEWS: StructureView[] = ['all', 'staging', 'production', 'reactions', 'reprocessing']

/** Old `?view=` values that still open the closest view (links pasted in
 * Discord). Freight and Market are corner icons on the cards now, not views. */
const VIEW_ALIASES: Record<string, StructureView> = {
    industry: 'production',
}

export function parse_structure_view(requested: string | null): StructureView {
    const name = requested ?? 'all'
    if ((STRUCTURE_VIEWS as string[]).includes(name)) return name as StructureView
    return VIEW_ALIASES[name] ?? 'all'
}

export type StructureFlag = 'home' | 'deployment' | 'fleets' | 'freight' | 'freight_route' | 'market' | 'industry_delivery'

/** Status tags the site derives from EveLocation. Browse cards show Home and
 * Deployment as a banner instead, so they ask for the tags without them
 * (`banner: false`). Open industry orders are not a tag: the location page
 * has its own Industry orders tool. Industry delivery is a hero tag only,
 * and never on the staging: orders always deliver there. */
export function structure_flags(
    card: Pick<StructureLocationCard, 'staging' | 'deployment' | 'fleets' | 'freight' | 'freight_route' | 'market'> & Partial<Pick<StructureLocationCard, 'industry_delivery'>>,
    { banner = true }: { banner?: boolean } = {},
) {
    const flags: { kind: StructureFlag, count?: number }[] = []
    if (banner && card.staging) flags.push({ kind: 'home' })
    if (banner && card.deployment) flags.push({ kind: 'deployment' })
    if (card.fleets) flags.push({ kind: 'fleets' })
    if (card.freight) flags.push({ kind: 'freight' })
    if (card.freight_route) flags.push({ kind: 'freight_route' })
    if (card.market) flags.push({ kind: 'market' })
    if (banner && card.industry_delivery && !card.staging) flags.push({ kind: 'industry_delivery' })
    return flags
}

/** The site's own icons for the corner tags on a card. */
export const FLAG_ICONS: Record<StructureFlag, string> = {
    home: '/images/icons/48px-Structurebrowser.png',
    deployment: '/images/icons/48px-Structurebrowser.png',
    fleets: '/images/icons/48px-Fleet.png',
    freight: '/images/icons/48px-Cargo.png',
    freight_route: '/images/icons/48px-Map.png',
    market: '/images/icons/48px-Market.png',
    industry_delivery: '/images/icons/48px-Industry.png',
}

/** EVE icons for what a rig builds: ship-tree class symbols for hulls, item
 * icons for the rest. Battleship and titan symbols are left out on purpose:
 * they are chevrons, like the tier marks next to them. */
const RIG_USE_ICONS: Record<string, () => string> = {
    subcap: () => '/images/icons/ships/Isis_cruiser.png',
    capital: () => '/images/icons/ships/Isis_capital.png',
    components: () => get_item_icon(21037, 64),
    research: () => get_item_icon(20424, 64),
    reactions: () => get_item_icon(16673, 64),
    reprocessing: () => get_item_icon(1230, 64),
    modules: () => get_item_icon(2048, 64),
}

export function rig_use_icon(use: string) {
    return (RIG_USE_ICONS[use] ?? (() => '/images/icons/48px-Icon_fit_rig.png'))()
}

const TIER_LEVEL: Record<string, number> = { T1: 1, T2: 2, Faction: 3 }

/** One chevron per tier up to the best tier this rig comes in; filled up to
 * the fitted tier. */
export function rig_steps(rig: Pick<StructureLocationModule, 'tier' | 'best_tier'>) {
    const level = TIER_LEVEL[rig.tier] ?? 1
    const best = TIER_LEVEL[rig.best_tier] ?? 2
    return Array.from({ length: Math.max(best, level) }, (_, index) => index < level)
}

/** 0.1309 → "13.09%", 0.0075 → "0.75%", 0.01 → "1%". */
export function percent(fraction: number | null | undefined, digits = 2) {
    if (fraction === null || fraction === undefined) return null
    const value = (fraction * 100).toFixed(digits).replace(/\.?0+$/, '')
    return `${value}%`
}

/** 50_000_000 → "50m". */
export function short_isk(isk: number) {
    if (isk >= 1_000_000_000) return `${+(isk / 1_000_000_000).toFixed(1)}b`
    if (isk >= 1_000_000) return `${+(isk / 1_000_000).toFixed(1)}m`
    if (isk >= 1_000) return `${+(isk / 1_000).toFixed(1)}k`
    return String(isk)
}

/** "Standup XL-Set Ship Manufacturing Efficiency I" → "Ship Manufacturing Efficiency I". */
export function rig_title(name: string) {
    return name.replace(/^Standup (M|L|XL)-Set /, '')
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
        default: return true
    }
}

/** CSS colour token for a system's security status, as EVE colours it. */
export function security_colour(security: number | null | undefined) {
    if (security === null || security === undefined) return 'var(--faded)'
    if (security >= 0.95) return 'var(--security-status-1)'
    if (security <= 0) return 'var(--security-status-null)'
    const step = Math.max(1, Math.min(9, Math.round(security * 10)))
    return `var(--security-status-point-${step})`
}

export function security_label(security: number | null | undefined) {
    if (security === null || security === undefined) return ''
    return (Math.round(security * 10) / 10).toFixed(1)
}
