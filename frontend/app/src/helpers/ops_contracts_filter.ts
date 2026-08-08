export type OpsContractsCriteriaId =
    | 'unstocked'
    | 'low_stock'
    | 'in_stock'
    | 'overstocked'

export type OpsContractsOrderById =
    | 'stock_fill'
    | 'volume_28d'
    | 'fleets_remaining'

export type OpsContractsSortDirection = 'asc' | 'desc'

export type OpsContractsStockStatus = OpsContractsCriteriaId

export const OPS_CONTRACTS_NO_DOCTRINE = 'none'

export const OPS_CONTRACTS_DEFAULT_CRITERIA: readonly OpsContractsCriteriaId[] = [
    'unstocked',
    'low_stock',
]

export const OPS_CONTRACTS_DEFAULT_ORDER_BY: OpsContractsOrderById = 'stock_fill'

/** First-click / initial direction for each order-by key. */
export const OPS_CONTRACTS_DEFAULT_DIRECTIONS: Record<
    OpsContractsOrderById,
    OpsContractsSortDirection
> = {
    stock_fill: 'desc',
    volume_28d: 'desc',
    fleets_remaining: 'asc',
}

export const OPS_CONTRACTS_DEFAULT_ORDER_DIR: OpsContractsSortDirection =
    OPS_CONTRACTS_DEFAULT_DIRECTIONS[OPS_CONTRACTS_DEFAULT_ORDER_BY]

export interface OpsContractsFilterRow {
    fitting_id: number
    title?: string
    /** Stock bucket from qty vs target; null when there is no expectation. */
    stock_status: OpsContractsStockStatus | null
    doctrine_ids: number[]
    fill_pct?: number | null
    volume_28d?: number
    fleets_remaining?: number | null
    fleets_per_month?: number | null
}

const CRITERIA_IDS = new Set<string>([
    'unstocked',
    'low_stock',
    'in_stock',
    'overstocked',
])

const ORDER_BY_IDS = new Set<string>([
    'stock_fill',
    'volume_28d',
    'fleets_remaining',
])

function is_order_by_id(value: string): value is OpsContractsOrderById {
    return ORDER_BY_IDS.has(value)
}

function is_sort_direction(value: string): value is OpsContractsSortDirection {
    return value === 'asc' || value === 'desc'
}

/**
 * Map outstanding qty vs expectation to a Criteria chip id.
 * Returns null when there is no positive target quantity.
 */
export function ops_contracts_stock_status(
    current_quantity: number,
    desired_quantity: number,
): OpsContractsStockStatus | null {
    if (desired_quantity <= 0)
        return null
    if (current_quantity <= 0)
        return 'unstocked'
    if (current_quantity < desired_quantity)
        return 'low_stock'
    if (current_quantity > desired_quantity)
        return 'overstocked'
    return 'in_stock'
}

export function ops_contracts_default_direction(
    order_by: OpsContractsOrderById | string = OPS_CONTRACTS_DEFAULT_ORDER_BY,
): OpsContractsSortDirection {
    const key = is_order_by_id(order_by)
        ? order_by
        : OPS_CONTRACTS_DEFAULT_ORDER_BY
    return OPS_CONTRACTS_DEFAULT_DIRECTIONS[key]
}

/**
 * Next order-by state after clicking a pill.
 * Same active key → flip direction; new key → select with that key's default direction.
 */
export function ops_contracts_next_order_state(
    current_order_by: OpsContractsOrderById | string,
    current_direction: OpsContractsSortDirection | string,
    clicked_id: string,
): {
    order_by: OpsContractsOrderById
    direction: OpsContractsSortDirection
} {
    const current_key = is_order_by_id(current_order_by)
        ? current_order_by
        : OPS_CONTRACTS_DEFAULT_ORDER_BY
    const current_dir = is_sort_direction(current_direction)
        ? current_direction
        : ops_contracts_default_direction(current_key)

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
        direction: ops_contracts_default_direction(clicked_id),
    }
}

/**
 * Compare numeric keys with missing values always last, independent of direction.
 */
function compare_numeric(
    a_val: number | null,
    b_val: number | null,
    direction: OpsContractsSortDirection,
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

function fill_pct_value(row: OpsContractsFilterRow): number | null {
    return row.fill_pct ?? null
}

function compare_by_order(
    a: OpsContractsFilterRow,
    b: OpsContractsFilterRow,
    order_by: OpsContractsOrderById,
    direction: OpsContractsSortDirection,
): number {
    switch (order_by) {
        case 'stock_fill':
            return compare_numeric(
                fill_pct_value(a),
                fill_pct_value(b),
                direction,
            )
        case 'volume_28d':
            return compare_numeric(
                a.volume_28d ?? 0,
                b.volume_28d ?? 0,
                direction,
            )
        case 'fleets_remaining':
            return compare_numeric(
                a.fleets_remaining ?? null,
                b.fleets_remaining ?? null,
                direction,
            )
        default: {
            const _exhaustive: never = order_by
            return _exhaustive
        }
    }
}

/**
 * Compare rows for All Contracts order-by pills (single-select + direction).
 * Defaults: stock fill desc (most stocked first); volume 28d desc; fleets remaining asc.
 * Missing fill / fleets remaining always sort last.
 * Ties break alphabetically by title.
 */
export function ops_contracts_compare_rows(
    a: OpsContractsFilterRow,
    b: OpsContractsFilterRow,
    order_by: OpsContractsOrderById | string = OPS_CONTRACTS_DEFAULT_ORDER_BY,
    direction?: OpsContractsSortDirection | string,
): number {
    const key = is_order_by_id(order_by)
        ? order_by
        : OPS_CONTRACTS_DEFAULT_ORDER_BY
    const dir = direction != null && is_sort_direction(direction)
        ? direction
        : ops_contracts_default_direction(key)
    const primary = compare_by_order(a, b, key, dir)
    if (primary !== 0)
        return primary

    return (a.title ?? '').localeCompare(b.title ?? '')
}

function doctrine_matches(
    row: OpsContractsFilterRow,
    doctrines: readonly string[],
): boolean {
    if (doctrines.length === 0)
        return true

    const ids = row.doctrine_ids ?? []
    const has_none = ids.length === 0

    return doctrines.some(id => {
        if (id === OPS_CONTRACTS_NO_DOCTRINE)
            return has_none
        const doctrine_id = Number(id)
        return !Number.isNaN(doctrine_id) && ids.includes(doctrine_id)
    })
}

/**
 * Contract row visibility.
 * Criteria chips (Unstocked / Low Stock / In Stock / Overstocked) OR within the group.
 * Rows with no target quantity match no stock criteria (hidden unless criteria empty).
 * Doctrine chips OR within the group (including "none" for fittings with no doctrine).
 * Search is a case-insensitive substring on title.
 */
export function ops_contracts_row_visible(
    row: OpsContractsFilterRow,
    criteria: readonly string[],
    doctrines: readonly string[],
    search = '',
): boolean {
    const stock_selected = criteria.filter(id => CRITERIA_IDS.has(id))
    const criteria_ok = stock_selected.length === 0
        || (row.stock_status != null && stock_selected.includes(row.stock_status))
    const doctrine_ok = doctrine_matches(row, doctrines)
    const query = search.trim().toLowerCase()
    const search_ok = query === ''
        || (row.title ?? '').toLowerCase().includes(query)
    return criteria_ok && doctrine_ok && search_ok
}
