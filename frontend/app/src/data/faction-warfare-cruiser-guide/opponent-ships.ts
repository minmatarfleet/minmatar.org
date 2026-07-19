export const cruiserGuideShips = {
    arbitrator: { shipId: 628, shipName: 'Arbitrator' },
    augni: { shipId: 29337, shipName: 'Augoror Navy Issue' },
    maller: { shipId: 624, shipName: 'Maller' },
    omen: { shipId: 2006, shipName: 'Omen' },
    omenni: { shipId: 17709, shipName: 'Omen Navy Issue' },
    caracalni: { shipId: 17634, shipName: 'Caracal Navy Issue' },
    ospreyni: { shipId: 29340, shipName: 'Osprey Navy Issue' },
    eni: { shipId: 29344, shipName: 'Exequror Navy Issue' },
    vexor: { shipId: 626, shipName: 'Vexor' },
    vni: { shipId: 17843, shipName: 'Vexor Navy Issue' },
    bellicose: { shipId: 630, shipName: 'Bellicose' },
    scythefi: { shipId: 29336, shipName: 'Scythe Fleet Issue' },
    stabber: { shipId: 622, shipName: 'Stabber' },
    stabberfi: { shipId: 17713, shipName: 'Stabber Fleet Issue' },
} as const

export type ResolvedOpponentShip = {
    shipId: number
    shipName: string
}

/** Exact guide fit display names → hull (from fittings.ts). */
const fitNameToShip: Record<string, ResolvedOpponentShip> = {
    'Long Point Arbitrator': cruiserGuideShips.arbitrator,
    'Brawl Arbitrator': cruiserGuideShips.arbitrator,
    'TD Support Arbitrator': cruiserGuideShips.arbitrator,
    'Polarized Augoror Navy Issue': cruiserGuideShips.augni,
    'Pulse Augoror Navy Issue': cruiserGuideShips.augni,
    'Pulse Maller': cruiserGuideShips.maller,
    'Beam Omen': cruiserGuideShips.omen,
    'Pulse Omen': cruiserGuideShips.omen,
    'Sniper Omen': cruiserGuideShips.omen,
    'Kite Omen Navy Issue': cruiserGuideShips.omenni,
    'Beam Omen Navy Issue': cruiserGuideShips.omenni,
    'Pulse Omen Navy Issue': cruiserGuideShips.omenni,
    'HAM Caracal Navy Issue': cruiserGuideShips.caracalni,
    '2X Neut HAM Osprey Navy Issue': cruiserGuideShips.ospreyni,
    'RHML Osprey Navy Issue': cruiserGuideShips.ospreyni,
    'Blaster Exequror Navy Issue': cruiserGuideShips.eni,
    '250mm Rail Exequror Navy Issue': cruiserGuideShips.eni,
    'Dual Plate Electron Exequror Navy Issue': cruiserGuideShips.eni,
    'Neut Vexor': cruiserGuideShips.vexor,
    'Blaster Vexor': cruiserGuideShips.vexor,
    'Dual Rep Vexor Navy Issue': cruiserGuideShips.vni,
    'HAM Bellicose': cruiserGuideShips.bellicose,
    'XLASB HAM Bellicose': cruiserGuideShips.bellicose,
    'Dual Prop Scythe Fleet Issue': cruiserGuideShips.scythefi,
    'Armor RLML Scythe Fleet Issue': cruiserGuideShips.scythefi,
    'RLML XLASB Scythe Fleet Issue': cruiserGuideShips.scythefi,
    'AB XLASB Stabber': cruiserGuideShips.stabber,
    'Vulcan Stabber': cruiserGuideShips.stabber,
    'Dual Prop Stabber Fleet Issue': cruiserGuideShips.stabberfi,
}

/** Map free-text matchup labels (guide fit names) to a guide hull for icons. */
export function resolveMatchupOpponentShip(
    opponent: string,
    selfShip?: ResolvedOpponentShip,
): ResolvedOpponentShip | null {
    const trimmed = opponent.trim()
    const lower = trimmed.toLowerCase()

    if (lower.includes('self') || lower.includes('mirror') || lower === 'tbd') {
        return selfShip ?? null
    }

    // Non-roster punch-up/down that destroyer/frigate guides also leave iconless.
    if (
        lower.includes('frigate') ||
        lower.includes('destroyer') ||
        lower.includes('dessie') ||
        lower.includes('battlecruiser')
    ) {
        return null
    }

    const exact = fitNameToShip[trimmed]
    if (exact) {
        return exact
    }

    if (lower.includes('arbitrator') || lower.includes('arby')) {
        return cruiserGuideShips.arbitrator
    }

    if (lower.includes('exeq') || lower.includes('eni')) {
        return cruiserGuideShips.eni
    }

    if (lower.includes('vexor navy') || lower.includes('vni') || lower.includes('dual rep')) {
        return cruiserGuideShips.vni
    }

    if (lower.includes('augoror') || lower.includes('augni') || lower.includes('polarized')) {
        return cruiserGuideShips.augni
    }

    if (lower.includes('omen navy') || lower.includes('omenni')) {
        return cruiserGuideShips.omenni
    }

    if (lower.includes('caracal navy') || lower.includes('cni')) {
        return cruiserGuideShips.caracalni
    }

    if (lower.includes('osprey')) {
        return cruiserGuideShips.ospreyni
    }

    if (lower.includes('scythe')) {
        return cruiserGuideShips.scythefi
    }

    if (lower.includes('stabber fleet') || lower.includes('stabber fi')) {
        return cruiserGuideShips.stabberfi
    }

    if (lower.includes('bellicose')) {
        return cruiserGuideShips.bellicose
    }

    if (lower.includes('stabber')) {
        return cruiserGuideShips.stabber
    }

    if (lower.includes('vexor')) {
        return cruiserGuideShips.vexor
    }

    if (lower.includes('omen')) {
        return cruiserGuideShips.omen
    }

    if (lower.includes('maller')) {
        return cruiserGuideShips.maller
    }

    return null
}
