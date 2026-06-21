export const navyDestroyerShips = {
    catalyst: { shipId: 73796, shipName: 'Catalyst Navy Issue' },
    coercer: { shipId: 73789, shipName: 'Coercer Navy Issue' },
    thrasher: { shipId: 73794, shipName: 'Thrasher Fleet Issue' },
    cormorant: { shipId: 73795, shipName: 'Cormorant Navy Issue' },
} as const

export type ResolvedOpponentShip = {
    shipId: number
    shipName: string
}

/** Map free-text matchup labels to a navy destroyer hull for icons. */
export function resolveMatchupOpponentShip(
    opponent: string,
    selfShip?: ResolvedOpponentShip,
): ResolvedOpponentShip | null {
    const lower = opponent.toLowerCase()

    if (lower.includes('self')) {
        return selfShip ?? null
    }

    if (lower.includes('all brawl') || lower.includes('all kiting') || lower.includes('general 1v1')) {
        return null
    }

    if (lower.includes('tfi') || lower.includes('thrasher')) {
        return navyDestroyerShips.thrasher
    }

    if (lower.includes('coercer')) {
        return navyDestroyerShips.coercer
    }

    if (lower.includes('catni') || lower.includes('catalyst')) {
        return navyDestroyerShips.catalyst
    }

    if (lower.includes('corm')) {
        return navyDestroyerShips.cormorant
    }

    return null
}
