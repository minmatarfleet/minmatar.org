import type {
    BurstKind,
    FleetCompositionEntry,
    FleetFitRoles,
    FleetLinkCoverage,
    FleetRoleCoverage,
} from '@helpers/api.minmatar.org/fleets'

export const BURST_KINDS:BurstKind[] = ['armor', 'shield', 'skirmish', 'information', 'mining']

export interface LinkRow extends FleetLinkCoverage {
    /** Composition ships that can run this kind. */
    ship_names: string[]
}

/** Distinct ship names in the composition whose fit matches. */
export const ships_for_role = (
    composition:FleetCompositionEntry[],
    matches:(entry:FleetCompositionEntry) => boolean,
):string[] => [ ...new Set(composition.filter(matches).map(entry => entry.ship_name || entry.name)) ]

/**
 * Link rows worth showing: kinds some composition fit can run, plus any kind
 * a pilot already brings. A doctrine without links ships shows none.
 */
export const link_kinds = (
    roles:FleetRoleCoverage,
    composition:FleetCompositionEntry[],
):LinkRow[] => roles.links
    .map(row => ({
        ...row,
        ship_names: ships_for_role(composition, entry => (entry.fit_roles?.bursts_fitted?.[row.kind] ?? 0) > 0),
    }))
    .filter(row => row.ship_names.length > 0 || row.pilots.length > 0)

/** Cynos the roles list asks for. */
export const CYNOS_WANTED = 2

export interface RoleTally {
    /** Rows with a target: Logi FC, cynos (when the fits carry one), each link kind. */
    total: number
    filled: number
    /** Labels of the rows still short, in list order. */
    open: string[]
}

/**
 * How many roles with a target are filled. The roles list and the Overview's
 * "Before form-up" card both count this way, so they always agree.
 */
export const role_tally = (
    roles:FleetRoleCoverage,
    composition:FleetCompositionEntry[],
    labels:{ logi_fc:string, cynos:string },
):RoleTally => {
    const show_cynos = ships_for_role(composition, entry => entry.fit_roles?.cyno ?? false).length > 0 || roles.cynos.length > 0
    const rows = [
        { label: labels.logi_fc, filled: roles.logi_fc.length >= 1 },
        ...(show_cynos ? [{ label: labels.cynos, filled: roles.cynos.length >= CYNOS_WANTED }] : []),
        ...link_kinds(roles, composition).map(row => ({ label: row.label, filled: row.pilots.length >= 1 })),
    ]
    return {
        total: rows.length,
        filled: rows.filter(row => row.filled).length,
        open: rows.filter(row => !row.filled).map(row => row.label),
    }
}

/** The fit's online bursts as per-kind counts (the pick form's defaults). */
export const default_burst_counts = (roles:FleetFitRoles):Partial<Record<BurstKind, number>> =>
    ({ ...roles.bursts_online })

/** Per-kind counts → a burst list in canonical order. */
export const bursts_from_counts = (counts:Partial<Record<BurstKind, number>>):BurstKind[] =>
    BURST_KINDS.flatMap(kind => Array(Math.max(0, counts[kind] ?? 0)).fill(kind))

/** A burst list → per-kind counts. */
export const counts_from_bursts = (bursts:BurstKind[]):Partial<Record<BurstKind, number>> =>
    bursts.reduce((counts, kind) => ({ ...counts, [kind]: (counts[kind] ?? 0) + 1 }), {} as Partial<Record<BurstKind, number>>)

/** "Skirmish · Information ×2" for a pilot's picked bursts. */
export const bursts_summary = (bursts:BurstKind[], labels:Record<BurstKind, string>):string => {
    const counts = counts_from_bursts(bursts)
    return BURST_KINDS
        .filter(kind => counts[kind])
        .map(kind => counts[kind]! > 1 ? `${labels[kind]} ×${counts[kind]}` : labels[kind])
        .join(' · ')
}
