export const navyDestroyerShips = {
    catalyst: { shipId: 73796, shipName: 'Catalyst Navy Issue' },
    coercer: { shipId: 73789, shipName: 'Coercer Navy Issue' },
    thrasher: { shipId: 73794, shipName: 'Thrasher Fleet Issue' },
    cormorant: { shipId: 73795, shipName: 'Cormorant Navy Issue' },
    talwar: { shipId: 91858, shipName: 'Talwar Fleet Issue' },
    algos: { shipId: 32872, shipName: 'Algos' },
    thrasherT1: { shipId: 16242, shipName: 'Thrasher' },
    coercerT1: { shipId: 16236, shipName: 'Coercer' },
    dragoon: { shipId: 32874, shipName: 'Dragoon' },
} as const

export type ResolvedOpponentShip = {
    shipId: number
    shipName: string
}

/** Map free-text matchup labels to a destroyer hull for icons. */
export function resolveMatchupOpponentShip(
    opponent: string,
    selfShip?: ResolvedOpponentShip,
): ResolvedOpponentShip | null {
    const lower = opponent.toLowerCase()

    if (lower.includes('self') || lower.includes('mirror')) {
        return selfShip ?? null
    }

    if (lower.includes('all brawl') || lower.includes('all kiting') || lower.includes('general 1v1')) {
        return null
    }

    if (lower.includes('frigate') || lower.includes('comet') || lower.includes('hookbill')) {
        return null
    }

    if (lower.includes('talfi') || lower.includes('talwar')) {
        return navyDestroyerShips.talwar
    }

    if (lower.includes('thrasher fleet') || lower.includes('tfi')) {
        return navyDestroyerShips.thrasher
    }

    if (lower.includes('coercer navy') || lower.includes('coercerni') || lower.includes('coercer ni')) {
        return navyDestroyerShips.coercer
    }

    if (lower.includes('catni') || lower.includes('catalyst navy') || lower.includes('catalyst')) {
        return navyDestroyerShips.catalyst
    }

    if (lower.includes('corm')) {
        return navyDestroyerShips.cormorant
    }

    if (lower.includes('algos')) {
        return navyDestroyerShips.algos
    }

    if (lower.includes('dragoon')) {
        return navyDestroyerShips.dragoon
    }

    if (lower.includes('thrasher')) {
        return navyDestroyerShips.thrasherT1
    }

    if (lower.includes('coercer')) {
        return navyDestroyerShips.coercerT1
    }

    return null
}
