export const navyFrigateShips = {
    hookbill: { shipId: 17619, shipName: 'Caldari Navy Hookbill' },
    comet: { shipId: 17841, shipName: 'Federation Navy Comet' },
    slicer: { shipId: 17703, shipName: 'Imperial Navy Slicer' },
    firetail: { shipId: 17812, shipName: 'Republic Fleet Firetail' },
    vigil: { shipId: 37454, shipName: 'Vigil Fleet Issue' },
    rifter: { shipId: 587, shipName: 'Rifter' },
    tristan: { shipId: 593, shipName: 'Tristan' },
    breacher: { shipId: 598, shipName: 'Breacher' },
} as const

export type ResolvedOpponentShip = {
    shipId: number
    shipName: string
}

/** Map free-text matchup labels to a frigate hull for icons. */
export function resolveMatchupOpponentShip(
    opponent: string,
    selfShip?: ResolvedOpponentShip,
): ResolvedOpponentShip | null {
    const lower = opponent.toLowerCase()

    if (lower.includes('self') || lower.includes('mirror')) {
        return selfShip ?? null
    }

    if (lower.includes('hookbill')) {
        return navyFrigateShips.hookbill
    }

    if (lower.includes('comet')) {
        return navyFrigateShips.comet
    }

    if (lower.includes('slicer')) {
        return navyFrigateShips.slicer
    }

    if (lower.includes('firetail')) {
        return navyFrigateShips.firetail
    }

    if (lower.includes('vigil')) {
        return navyFrigateShips.vigil
    }

    if (lower.includes('rifter')) {
        return navyFrigateShips.rifter
    }

    if (lower.includes('tristan')) {
        return navyFrigateShips.tristan
    }

    if (lower.includes('breacher')) {
        return navyFrigateShips.breacher
    }

    return null
}
