/**
 * EVE ship groups (SDE invGroups.groupName, category Ships), in the order the
 * fittings page, fitting finder and fleet pickers list them.
 *
 * One table for every frontend use: list order, the doctrine size bucket,
 * the 3D viewer camera weight and the group icon. Names must match the SDE
 * exactly (testing/helpers/ship_groups.test.ts checks them).
 */

export const SHIP_SIZES = [
    'frigate',
    'destroyer',
    'cruiser',
    'battlecruiser',
    'battleship',
    'capital',
    'supercapital',
] as const

export type ShipSize = typeof SHIP_SIZES[number]

export interface ShipGroup {
    group: string
    /**
     * Doctrine sort bucket. Mining and industrial hulls sit with the combat
     * hulls of their size here, but after the titans in the list order.
     */
    size: ShipSize
    /** Camera interpolation decay for the 3D fitting viewer. */
    weight: number
    /** File in /images/icons/ships/, or null for no icon. */
    icon: string | null
    /** Counts as a capital hull in fleet compositions. */
    capital?: boolean
}

const group = (
    name: string,
    size: ShipSize,
    weight: number,
    icon: string | null,
    capital = false,
): ShipGroup => ({ group: name, size, weight, icon, capital })

export const SHIP_GROUPS: readonly ShipGroup[] = [
    group('Frigate', 'frigate', 50, 'Isis_frigate.png'),
    group('Electronic Attack Ship', 'frigate', 50, 'Isis_frigate.png'),
    group('Assault Frigate', 'frigate', 50, 'Isis_frigate.png'),
    group('Logistics Frigate', 'frigate', 50, 'Isis_frigate.png'),
    group('Covert Ops', 'frigate', 50, 'Isis_frigate.png'),
    group('Stealth Bomber', 'frigate', 50, 'Isis_frigate.png'),
    group('Interceptor', 'frigate', 50, 'Isis_frigate.png'),
    group('Destroyer', 'destroyer', 100, 'Isis_destroyer.png'),
    group('Interdictor', 'destroyer', 100, 'Isis_destroyer.png'),
    group('Command Destroyer', 'destroyer', 100, 'Isis_destroyer.png'),
    group('Tactical Destroyer', 'destroyer', 100, 'Isis_destroyer.png'),
    group('Cruiser', 'cruiser', 200, 'Isis_cruiser.png'),
    group('Heavy Assault Cruiser', 'cruiser', 200, 'Isis_cruiser.png'),
    group('Heavy Interdiction Cruiser', 'cruiser', 200, 'Isis_cruiser.png'),
    group('Logistics', 'cruiser', 200, 'Isis_cruiser.png'),
    group('Strategic Cruiser', 'cruiser', 200, 'Isis_cruiser.png'),
    group('Force Recon Ship', 'cruiser', 200, 'Isis_cruiser.png'),
    group('Combat Recon Ship', 'cruiser', 200, 'Isis_cruiser.png'),
    group('Flag Cruiser', 'cruiser', 200, 'Isis_cruiser.png'),
    group('Combat Battlecruiser', 'battlecruiser', 300, 'Isis_battlecruiser.png'),
    group('Attack Battlecruiser', 'battlecruiser', 300, 'Isis_battlecruiser.png'),
    group('Command Ship', 'battlecruiser', 300, 'Isis_battlecruiser.png'),
    group('Battleship', 'battleship', 500, 'Isis_battleship.png'),
    group('Marauder', 'battleship', 500, 'Isis_battleship.png'),
    group('Black Ops', 'battleship', 500, 'Isis_battleship.png'),
    group('Dreadnought', 'capital', 700, 'Isis_capital.png', true),
    group('Lancer Dreadnought', 'capital', 700, 'Isis_capital.png', true),
    group('Carrier', 'capital', 600, 'Isis_supercapital.png', true),
    group('Force Auxiliary', 'capital', 700, 'Isis_supercapital.png', true),
    group('Supercarrier', 'supercapital', 700, 'Isis_supercarrier.png', true),
    group('Titan', 'supercapital', 900, 'Isis_titan.png', true),
    group('Expedition Frigate', 'frigate', 50, 'Isis_miningfrigate.png'),
    group('Mining Barge', 'cruiser', 100, 'Isis_miningbarge.png'),
    group('Exhumer', 'cruiser', 100, 'Isis_miningbarge.png'),
    group('Hauler', 'cruiser', 300, 'Isis_industrial.png'),
    group('Blockade Runner', 'battleship', 100, 'Isis_industrial.png'),
    group('Deep Space Transport', 'battleship', 100, 'Isis_industrial.png'),
    group('Freighter', 'capital', 500, 'Isis_industrial.png', true),
    group('Jump Freighter', 'capital', 500, 'Isis_freighter.png', true),
    group('Industrial Command Ship', 'capital', 700, 'Isis_industrialcommand.png'),
    group('Capital Industrial Ship', 'capital', 700, 'Isis_industrialcommand.png', true),
    group('Corvette', 'frigate', 50, null),
    group('Shuttle', 'frigate', 50, null),
    group('Prototype Exploration Ship', 'frigate', 50, null),
    group('Capsule', 'frigate', 50, null),
]

/** Camera weight for hulls whose group is unknown (or missing). */
export const DEFAULT_SHIP_WEIGHT = 50

const BY_NAME = new Map(SHIP_GROUPS.map((entry, index) => [entry.group, { ...entry, index }]))

/** Group names in list order. */
export const SHIP_GROUP_NAMES: readonly string[] = SHIP_GROUPS.map(entry => entry.group)

/** Position in the list order; unknown groups sort first (-1), as before. */
export const ship_group_index = (name: string | null | undefined): number =>
    BY_NAME.get(name ?? '')?.index ?? -1

/** Doctrine size bucket (0 = frigate ... 6 = supercapital), or null when unknown. */
export const ship_size_rank = (name: string | null | undefined): number | null => {
    const entry = BY_NAME.get(name ?? '')
    return entry ? SHIP_SIZES.indexOf(entry.size) : null
}

export const ship_weight = (name: string | null | undefined): number =>
    BY_NAME.get(name ?? '')?.weight ?? DEFAULT_SHIP_WEIGHT

export const ship_group_icon = (name: string | null | undefined): string | null =>
    BY_NAME.get(name ?? '')?.icon ?? null

export const is_capital_group = (name: string | null | undefined): boolean =>
    BY_NAME.get(name ?? '')?.capital ?? false
