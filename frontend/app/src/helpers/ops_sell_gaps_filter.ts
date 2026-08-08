export type OpsSellGapsCriteriaId =
    | 'out_of_stock'
    | 'understocked'
    | 'overpriced'
    | 'in_stock'

export type OpsSellGapsOrderById =
    | 'days_of_stock'
    | 'markup'
    | 'volume_7d'

export type OpsSellGapsSortDirection = 'asc' | 'desc'

export const OPS_SELL_GAPS_DEFAULT_ORDER_BY: OpsSellGapsOrderById = 'days_of_stock'

/** First-click / initial direction for each order-by key. */
export const OPS_SELL_GAPS_DEFAULT_DIRECTIONS: Record<
    OpsSellGapsOrderById,
    OpsSellGapsSortDirection
> = {
    days_of_stock: 'asc',
    markup: 'desc',
    volume_7d: 'desc',
}

export const OPS_SELL_GAPS_DEFAULT_ORDER_DIR: OpsSellGapsSortDirection =
    OPS_SELL_GAPS_DEFAULT_DIRECTIONS[OPS_SELL_GAPS_DEFAULT_ORDER_BY]

export interface OpsSellGapsFilterRow {
    item_name?: string
    item_type: string
    item_variant: string
    flags?: string[]
    current_quantity?: number
    shortfall?: number
    weekly_units?: number
    days_of_stock?: number | null
    avg_markup_pct?: number | null
}

const STOCK_CRITERIA = new Set<string>([
    'out_of_stock',
    'understocked',
    'in_stock',
])

const ORDER_BY_IDS = new Set<string>([
    'days_of_stock',
    'markup',
    'volume_7d',
])

function is_order_by_id(value: string): value is OpsSellGapsOrderById {
    return ORDER_BY_IDS.has(value)
}

function is_sort_direction(value: string): value is OpsSellGapsSortDirection {
    return value === 'asc' || value === 'desc'
}

export function ops_sell_gaps_default_direction(
    order_by: OpsSellGapsOrderById | string = OPS_SELL_GAPS_DEFAULT_ORDER_BY,
): OpsSellGapsSortDirection {
    const key = is_order_by_id(order_by)
        ? order_by
        : OPS_SELL_GAPS_DEFAULT_ORDER_BY
    return OPS_SELL_GAPS_DEFAULT_DIRECTIONS[key]
}

/**
 * Next order-by state after clicking a pill.
 * Same active key → flip direction; new key → select with that key's default direction.
 */
export function ops_sell_gaps_next_order_state(
    current_order_by: OpsSellGapsOrderById | string,
    current_direction: OpsSellGapsSortDirection | string,
    clicked_id: string,
): {
    order_by: OpsSellGapsOrderById
    direction: OpsSellGapsSortDirection
} {
    const current_key = is_order_by_id(current_order_by)
        ? current_order_by
        : OPS_SELL_GAPS_DEFAULT_ORDER_BY
    const current_dir = is_sort_direction(current_direction)
        ? current_direction
        : ops_sell_gaps_default_direction(current_key)

    if (!is_order_by_id(clicked_id)) {
        return {
            order_by: current_key,
            direction: current_dir,
        }
    }

    if (clicked_id === current_key) {
        return {
            order_by: current_key,
            direction: current_dir === 'asc' ? 'desc' : 'asc',
        }
    }

    return {
        order_by: clicked_id,
        direction: ops_sell_gaps_default_direction(clicked_id),
    }
}

function days_of_stock_value(row: OpsSellGapsFilterRow): number | null {
    if (row.days_of_stock != null)
        return row.days_of_stock
    // Empty stock is most urgent (0 days). Unknown rate with listed qty is missing.
    if ((row.current_quantity ?? 0) <= 0)
        return 0
    return null
}

function markup_value(row: OpsSellGapsFilterRow): number | null {
    return row.avg_markup_pct ?? null
}

/**
 * Compare numeric keys with missing values always last, independent of direction.
 */
function compare_numeric(
    a_val: number | null,
    b_val: number | null,
    direction: OpsSellGapsSortDirection,
): number {
    const a_missing = a_val == null
    const b_missing = b_val == null
    if (a_missing && b_missing)
        return 0
    if (a_missing)
        return 1
    if (b_missing)
        return -1
    const asc = a_val - b_val
    return direction === 'asc' ? asc : -asc
}

function compare_by_order(
    a: OpsSellGapsFilterRow,
    b: OpsSellGapsFilterRow,
    order_by: OpsSellGapsOrderById,
    direction: OpsSellGapsSortDirection,
): number {
    switch (order_by) {
        case 'days_of_stock':
            return compare_numeric(
                days_of_stock_value(a),
                days_of_stock_value(b),
                direction,
            )
        case 'markup':
            return compare_numeric(
                markup_value(a),
                markup_value(b),
                direction,
            )
        case 'volume_7d':
            return compare_numeric(
                a.weekly_units ?? 0,
                b.weekly_units ?? 0,
                direction,
            )
        default: {
            const _exhaustive: never = order_by
            return _exhaustive
        }
    }
}

/**
 * Compare rows for Stock order-by pills (single-select + direction).
 * Defaults: days of stock asc (least remaining); markup / volume 7d desc.
 * Missing markup / unknown days-of-stock always sort last.
 * Ties break alphabetically by item name.
 */
export function ops_sell_gaps_compare_rows(
    a: OpsSellGapsFilterRow,
    b: OpsSellGapsFilterRow,
    order_by: OpsSellGapsOrderById | string = OPS_SELL_GAPS_DEFAULT_ORDER_BY,
    direction?: OpsSellGapsSortDirection | string,
): number {
    const key = is_order_by_id(order_by)
        ? order_by
        : OPS_SELL_GAPS_DEFAULT_ORDER_BY
    const dir = direction != null && is_sort_direction(direction)
        ? direction
        : ops_sell_gaps_default_direction(key)
    const primary = compare_by_order(a, b, key, dir)
    if (primary !== 0)
        return primary

    return (a.item_name ?? '').localeCompare(b.item_name ?? '')
}

/**
 * Stock row visibility.
 * Stock-status Criteria chips (Out of Stock / Understocked / In Stock) OR
 * within the group. Other Criteria (e.g. Overpriced) AND with that group.
 * Type / Variant stay OR-within-group.
 * Search is a case-insensitive substring on item_name.
 */
export function ops_sell_gaps_row_visible(
    row: OpsSellGapsFilterRow,
    criteria: readonly string[],
    types: readonly string[],
    variants: readonly string[],
    search = '',
): boolean {
    const flags = row.flags ?? []
    const stock_selected = criteria.filter(id => STOCK_CRITERIA.has(id))
    const other_selected = criteria.filter(id => !STOCK_CRITERIA.has(id))
    const stock_ok = stock_selected.length === 0
        || stock_selected.some(id => flags.includes(id))
    const other_ok = other_selected.every(id => flags.includes(id))
    const criteria_ok = stock_ok && other_ok
    const type_ok = types.length === 0
        || types.includes(row.item_type)
    const variant_ok = variants.length === 0
        || variants.includes(row.item_variant)
    const query = search.trim().toLowerCase()
    const search_ok = query === ''
        || (row.item_name ?? '').toLowerCase().includes(query)
    return criteria_ok && type_ok && variant_ok && search_ok
}
