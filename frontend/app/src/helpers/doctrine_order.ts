import type { DoctrineType, DoctrineTypes, FittingItem } from '@dtypes/layout_components'

/** Hull groups, small to large. Order inside a size is the tie-break after tech level. */
const HULL_SIZES: readonly (readonly string[])[] = [
    [
        'Frigate',
        'Electronic Attack Ship',
        'Assault Frigate',
        'Logistics Frigate',
        'Covert Ops',
        'Stealth Bomber',
        'Interceptor',
        'Mining Frigate',
        'Expedition Frigate',
    ],
    [
        'Destroyer',
        'Interdictor',
        'Command Destroyer',
        'Tactical Destroyer',
    ],
    [
        'Cruiser',
        'Heavy Assault Cruiser',
        'Heavy Interdiction Cruiser',
        'Logistics',
        'Logistics Crusiers',
        'Strategic Cruiser',
        'Recon Ship',
        'Force Recon Ship',
        'Combat Recon Ship',
        'Mining Barge',
        'Industrial',
    ],
    [
        'Battlecruiser',
        'Combat Battlecruiser',
        'Attack Battlecruiser',
        'Command Ship',
    ],
    [
        'Battleship',
        'Marauder',
        'Black Ops',
        'Transport Ship',
    ],
    [
        'Capital',
        'Dreadnought',
        'Lancer Dreadnought',
        'Carrier',
        'Force Auxiliary',
        'Freighter',
        'Jump Freighters',
        'Industrial Command Ship',
    ],
    [
        'Super Capital',
        'Super Carrier',
        'Command Carrier',
        'Titan',
    ],
]

/** T1, then faction, then T2, then T3. */
const SHIP_META_ORDER = ['Tech I', 'Storyline', 'Faction', 'Tech II', 'Tech III']

/**
 * Same ship stays together: the non-strategic doctrine, then its strategic
 * counterpart, then experimental. Type is not a top-level group.
 */
const DOCTRINE_VARIANT_ORDER: readonly DoctrineTypes[] = [
    'non_strategic',
    'strategic',
    'experimental',
]

const UNKNOWN_RANK = 1000

const hull_size_rank = new Map<string, number>()
const hull_group_rank = new Map<string, number>()

HULL_SIZES.forEach((groups, size) => {
    groups.forEach((group, group_index) => {
        hull_size_rank.set(group, size)
        hull_group_rank.set(group, group_index)
    })
})

function meta_rank(meta: string | undefined): number {
    if (!meta) return 0
    const index = SHIP_META_ORDER.indexOf(meta)
    return index === -1 ? SHIP_META_ORDER.length : index
}

function variant_rank(type: DoctrineTypes): number {
    const index = DOCTRINE_VARIANT_ORDER.indexOf(type)
    return index === -1 ? DOCTRINE_VARIANT_ORDER.length : index
}

function fitting_ranks(fitting: FittingItem | undefined) {
    if (!fitting) {
        return {
            size: UNKNOWN_RANK,
            meta: UNKNOWN_RANK,
            group: UNKNOWN_RANK,
            ship_name: '',
            ship_id: 0,
        }
    }

    return {
        size: hull_size_rank.get(fitting.ship_type) ?? UNKNOWN_RANK,
        meta: meta_rank(fitting.ship_meta),
        group: hull_group_rank.get(fitting.ship_type) ?? UNKNOWN_RANK,
        ship_name: fitting.ship_name ?? '',
        ship_id: fitting.ship_id ?? 0,
    }
}

/** First primary fitting — the ship shown on the doctrine card. */
function sort_fitting(doctrine: DoctrineType): FittingItem | undefined {
    return doctrine.primary_fittings?.[0]
}

export function compare_doctrines(a: DoctrineType, b: DoctrineType): number {
    const a_rank = fitting_ranks(sort_fitting(a))
    const b_rank = fitting_ranks(sort_fitting(b))

    return a_rank.size - b_rank.size
        || a_rank.meta - b_rank.meta
        || a_rank.group - b_rank.group
        || a_rank.ship_name.localeCompare(b_rank.ship_name)
        || a_rank.ship_id - b_rank.ship_id
        || variant_rank(a.type) - variant_rank(b.type)
        || a.name.localeCompare(b.name)
        || a.id - b.id
}

export function sort_doctrines(doctrines: DoctrineType[]): DoctrineType[] {
    return doctrines.slice().sort(compare_doctrines)
}
