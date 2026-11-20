import type { StructureLocationCard } from '@dtypes/api.minmatar.org'

export type StructureView = 'all' | 'clones' | 'industry' | 'logistics' | 'market'
export const STRUCTURE_VIEWS: StructureView[] = ['all', 'clones', 'industry', 'logistics', 'market']

export type StructureFlag = 'staging' | 'fleets' | 'freight' | 'market' | 'orders'

/** Status tags the site derives from EveLocation and open orders. */
export function structure_flags(card: Pick<StructureLocationCard, 'staging' | 'fleets' | 'freight' | 'market' | 'industry_orders'>) {
    const flags: { kind: StructureFlag, count?: number }[] = []
    if (card.staging) flags.push({ kind: 'staging' })
    if (card.fleets) flags.push({ kind: 'fleets' })
    if (card.freight) flags.push({ kind: 'freight' })
    if (card.market) flags.push({ kind: 'market' })
    if (card.industry_orders > 0) flags.push({ kind: 'orders', count: card.industry_orders })
    return flags
}

/** Which locations each browse view shows. */
export function in_view(card: StructureLocationCard, view: StructureView) {
    switch (view) {
        case 'clones': return card.good_for.includes('clones') || card.services.some((s) => s.includes('Cloning')) || card.you.clones > 0
        case 'industry': return card.good_for.includes('industry') || card.rigs.length > 0
        case 'logistics': return card.good_for.includes('logistics') || card.freight || card.route_count > 0
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
