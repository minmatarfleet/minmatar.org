export type OpsSellGapsCriteriaId = 'understocked' | 'overpriced'

export interface OpsSellGapsFilterRow {
    item_type: string
    item_variant: string
    flags?: string[]
}

/**
 * Stock Gaps row visibility.
 * Criteria chips match visible tags (AND when multiple selected).
 * Type / Variant stay OR-within-group.
 */
export function ops_sell_gaps_row_visible(
    row: OpsSellGapsFilterRow,
    criteria: readonly string[],
    types: readonly string[],
    variants: readonly string[],
): boolean {
    const flags = row.flags ?? []
    const criteria_ok = criteria.length === 0
        || criteria.every(id => flags.includes(id))
    const type_ok = types.length === 0
        || types.includes(row.item_type)
    const variant_ok = variants.length === 0
        || variants.includes(row.item_variant)
    return criteria_ok && type_ok && variant_ok
}
