import type {
    BurstKind,
    FleetCompositionEntry,
    FleetFitRoles,
    FleetLinkCoverage,
    FleetRoleCoverage,
    FleetRolePilot,
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

/** Roles read from fits beyond links, cynos and logi, in list order. */
export const SHIP_ROLE_KINDS = ['interdiction', 'neuts', 'ecm'] as const
export type ShipRoleKind = typeof SHIP_ROLE_KINDS[number]

export interface ShipRoleRow {
    kind: ShipRoleKind
    pilots: FleetRolePilot[]
    /** Composition ships that fill this role. */
    ship_names: string[]
    /** Pilots the fleet wants (strategic fleets); undefined lists without a target. */
    wanted?: number
}

/**
 * Interdiction, neut and ECM rows worth showing: a composition fit fills the
 * role, or a pilot already brings it. The backend sets the wanted counts
 * (strategic fleets only); older backends send none, so the rows are lists.
 */
export const ship_role_rows = (
    roles:FleetRoleCoverage,
    composition:FleetCompositionEntry[],
):ShipRoleRow[] => SHIP_ROLE_KINDS
    .map(kind => {
        const wanted = roles.wanted?.[kind] ?? 0
        return {
            kind,
            pilots: roles[kind] ?? [],
            ship_names: ships_for_role(composition, entry => entry.fit_roles?.[kind] ?? false),
            wanted: wanted > 0 ? wanted : undefined,
        }
    })
    .filter(row => row.ship_names.length > 0 || row.pilots.length > 0)

export interface RoleTally {
    /** Rows with a target: Logi FC, cynos (when the fits carry one), each link kind, and interdiction / neuts / ECM on strategic fleets. */
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
    labels:{ logi_fc:string, cynos:string } & Partial<Record<ShipRoleKind, string>>,
):RoleTally => {
    const show_cynos = ships_for_role(composition, entry => entry.fit_roles?.cyno ?? false).length > 0 || roles.cynos.length > 0
    const rows = [
        { label: labels.logi_fc, filled: roles.logi_fc.length >= 1 },
        ...(show_cynos ? [{ label: labels.cynos, filled: roles.cynos.length >= CYNOS_WANTED }] : []),
        ...link_kinds(roles, composition).map(row => ({ label: row.label, filled: row.pilots.length >= 1 })),
        ...ship_role_rows(roles, composition)
            .filter(row => row.wanted !== undefined)
            .map(row => ({ label: labels[row.kind] ?? row.kind, filled: row.pilots.length >= row.wanted! })),
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
