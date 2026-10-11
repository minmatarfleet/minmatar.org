import type { LoyaltyOrdersQuery } from '@helpers/api.minmatar.org/loyalty'

export const LOYALTY_HISTORY_PAGE_SIZE = 20

/** Status filter values exposed to users (mapped to API statuses below). */
export const LOYALTY_HISTORY_STATUS_OPTIONS = ['completed', 'cancelled', 'all'] as const
export type LoyaltyHistoryStatus = typeof LOYALTY_HISTORY_STATUS_OPTIONS[number]
export const DEFAULT_LOYALTY_HISTORY_STATUS: LoyaltyHistoryStatus = 'completed'

const API_STATUSES: Record<LoyaltyHistoryStatus, string> = {
    completed: 'completed',
    cancelled: 'cancelled',
    all: 'completed,cancelled',
}

export interface LoyaltyHistoryFilters {
    page: number
    status: LoyaltyHistoryStatus
    loyalty_point_id: number | null
}

export function parse_loyalty_history_params(
    params: URLSearchParams,
): LoyaltyHistoryFilters {
    const page_raw = parseInt(params.get('page') ?? '1', 10)
    const page = Number.isFinite(page_raw) && page_raw > 0 ? page_raw : 1

    const status_raw = params.get('status') ?? ''
    const status = (LOYALTY_HISTORY_STATUS_OPTIONS as readonly string[]).includes(status_raw)
        ? status_raw as LoyaltyHistoryStatus
        : DEFAULT_LOYALTY_HISTORY_STATUS

    const currency_raw = params.get('loyalty_point_id') ?? ''
    const loyalty_point_id = /^\d+$/.test(currency_raw)
        ? parseInt(currency_raw, 10)
        : null

    return { page, status, loyalty_point_id }
}

export function loyalty_history_query(
    filters: LoyaltyHistoryFilters,
): LoyaltyOrdersQuery {
    return {
        status: API_STATUSES[filters.status],
        ordering: '-updated_at',
        limit: LOYALTY_HISTORY_PAGE_SIZE,
        offset: (filters.page - 1) * LOYALTY_HISTORY_PAGE_SIZE,
        ...(filters.loyalty_point_id != null
            ? { loyalty_point_id: filters.loyalty_point_id }
            : {}),
    }
}

/** Query-string params for the history partial (omits defaults). */
export function loyalty_history_partial_params(
    filters: LoyaltyHistoryFilters,
): Record<string, string> {
    const query: Record<string, string> = {}
    if (filters.page > 1) query.page = String(filters.page)
    if (filters.status !== DEFAULT_LOYALTY_HISTORY_STATUS) query.status = filters.status
    if (filters.loyalty_point_id != null)
        query.loyalty_point_id = String(filters.loyalty_point_id)
    return query
}
