/** Shared compressed-ore base names for buyback variant grouping. */

/** Low-value processing families first, then higher-value remaining ores. */
export const BUYBACK_ORE_BASES = [
    'Veldspar',
    'Scordite',
    'Pyroxeres',
    'Plagioclase',
    'Omber',
    'Kernite',
    'Jaspet',
    'Hemorphite',
    'Hedbergite',
    'Zeolites',
    'Sylvite',
    'Bitumens',
    'Coesite',
    'Gneiss',
    'Dark Ochre',
    'Crokite',
    'Mordunium',
    'Ytirium',
    'Eifyrium',
    'Ducinium',
    'Griemeer',
] as const

export const BUYBACK_STOCK_CATEGORIES = ['ore', 'p1', 'p2', 'p3', 'p4'] as const
export type BuybackStockCategory = (typeof BUYBACK_STOCK_CATEGORIES)[number]

const BUYBACK_ORE_BASE_SET = new Set<string>(BUYBACK_ORE_BASES)
const GRADE_SUFFIX_RE = /\s+(II|III|IV)-Grade$/
const MOON_PREFIX_RE = /^(Brimful|Glistening)\s+/
const PI_CATEGORY_RANK: Record<string, number> = {
    p1: 0,
    p2: 1,
    p3: 2,
    p4: 3,
}

export function buyback_ore_base(name: string): string | null {
    let rest = name.startsWith('Compressed ')
        ? name.slice('Compressed '.length)
        : name
    rest = rest.replace(GRADE_SUFFIX_RE, '')
    rest = rest.replace(MOON_PREFIX_RE, '')
    return BUYBACK_ORE_BASE_SET.has(rest) ? rest : null
}

export function compressed_buyback_ore_base(name: string): string | null {
    if (!name.startsWith('Compressed ')) return null
    return buyback_ore_base(name)
}

export interface JaniceStockRow {
    name: string
    quantity: number
}

export interface JaniceStockGroup {
    label: string
    quantity: number
    variants: JaniceStockRow[]
}

export interface StockGroupItem {
    type_id: number
    name: string
    category?: string | null
    quantity: number
    demand_status?: string | null
    isk_value?: number | null
}

export interface StockGroup {
    key: string
    label: string
    category: BuybackStockCategory | 'other'
    type_id: number
    quantity: number
    isk_value: number | null
    in_demand: boolean
    variants: StockGroupItem[]
}

/** Flatten displayed hangar rows so grouped ore copies real variant names. */
export function janice_tsv_from_stock_groups(groups: JaniceStockGroup[]): string {
    const rows: string[] = []
    for (const group of groups) {
        if (group.variants.length > 0) {
            for (const variant of group.variants) {
                if (variant.quantity > 0)
                    rows.push(`${variant.name}\t${variant.quantity}`)
            }
        } else if (group.quantity > 0) {
            rows.push(`${group.label}\t${group.quantity}`)
        }
    }
    return rows.join('\r\n')
}

function item_in_demand(item: StockGroupItem): boolean {
    if (!item.demand_status) return false
    return item.demand_status !== 'surplus'
}

function sum_isk(values: Array<number | null | undefined>): number | null {
    let total = 0
    let any = false
    for (const value of values) {
        if (value == null) continue
        total += value
        any = true
    }
    return any ? total : null
}

function is_pi_category(category: string | null | undefined): category is Exclude<BuybackStockCategory, 'ore'> {
    return category === 'p1' || category === 'p2' || category === 'p3' || category === 'p4'
}

function make_ore_group(base: string, variants: StockGroupItem[]): StockGroup {
    const sorted = variants.slice().sort((a, b) => a.name.localeCompare(b.name))
    const preferred =
        sorted.find((variant) => variant.name === `Compressed ${base}`)
        ?? sorted.find((variant) => variant.name === base)
        ?? sorted[0]
    return {
        key: `ore:${base}`,
        label: base,
        category: 'ore',
        type_id: preferred.type_id,
        quantity: sorted.reduce((sum, variant) => sum + variant.quantity, 0),
        isk_value: sum_isk(sorted.map((variant) => variant.isk_value)),
        in_demand: sorted.some(item_in_demand),
        variants: sorted,
    }
}

function make_single(
    item: StockGroupItem,
    category: StockGroup['category'],
): StockGroup {
    return {
        key: `type:${item.type_id}`,
        label: item.name,
        category,
        type_id: item.type_id,
        quantity: item.quantity,
        isk_value: item.isk_value ?? null,
        in_demand: item_in_demand(item),
        variants: [],
    }
}

function compare_pi(a: StockGroupItem, b: StockGroupItem): number {
    const rank_a = PI_CATEGORY_RANK[a.category ?? ''] ?? 99
    const rank_b = PI_CATEGORY_RANK[b.category ?? ''] ?? 99
    if (rank_a !== rank_b) return rank_a - rank_b
    return a.name.localeCompare(b.name)
}

/** Group hangar rows: ore families in tier order, then P1→P4. */
export function group_stock_items(items: StockGroupItem[]): StockGroup[] {
    const by_base = new Map<string, StockGroupItem[]>()
    const leftover_ores: StockGroupItem[] = []
    const leftover_pi: StockGroupItem[] = []
    const leftover_other: StockGroupItem[] = []

    for (const item of items) {
        const base = buyback_ore_base(item.name)
        if (base) {
            const group = by_base.get(base) ?? []
            group.push(item)
            by_base.set(base, group)
            continue
        }
        if (item.category === 'ore') {
            leftover_ores.push(item)
            continue
        }
        if (is_pi_category(item.category)) {
            leftover_pi.push(item)
            continue
        }
        leftover_other.push(item)
    }

    const ores = BUYBACK_ORE_BASES
        .filter((base) => by_base.has(base))
        .map((base) => make_ore_group(base, by_base.get(base) ?? []))

    leftover_ores.sort((a, b) => a.name.localeCompare(b.name))
    leftover_pi.sort(compare_pi)
    leftover_other.sort((a, b) => a.name.localeCompare(b.name))

    return [
        ...ores,
        ...leftover_ores.map((item) => make_single(item, 'ore')),
        ...leftover_pi.map((item) => {
            const category = item.category
            if (!is_pi_category(category)) return make_single(item, 'other')
            return make_single(item, category)
        }),
        ...leftover_other.map((item) => make_single(item, 'other')),
    ]
}
