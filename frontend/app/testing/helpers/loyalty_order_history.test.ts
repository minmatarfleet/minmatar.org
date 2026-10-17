import { describe, expect, it } from 'vitest'
import {
    LOYALTY_HISTORY_PAGE_SIZE,
    loyalty_history_partial_params,
    loyalty_history_query,
    parse_loyalty_history_params,
} from '@helpers/loyalty_order_history'

describe('parse_loyalty_history_params', () => {
    it('defaults to page 1, completed only', () => {
        expect(parse_loyalty_history_params(new URLSearchParams())).toEqual({
            page: 1,
            status: 'completed',
        })
    })

    it('reads page and status, ignoring a currency param', () => {
        const params = new URLSearchParams('page=3&status=all&loyalty_point_id=7')
        expect(parse_loyalty_history_params(params)).toEqual({
            page: 3,
            status: 'all',
        })
    })

    it('falls back on invalid values', () => {
        const params = new URLSearchParams('page=-2&status=open')
        expect(parse_loyalty_history_params(params)).toEqual({
            page: 1,
            status: 'completed',
        })
    })
})

describe('loyalty_history_query', () => {
    it('excludes cancelled orders by default and paginates', () => {
        expect(loyalty_history_query({ page: 2, status: 'completed' }, 4)).toEqual({
            status: 'completed',
            ordering: '-updated_at',
            limit: LOYALTY_HISTORY_PAGE_SIZE,
            offset: LOYALTY_HISTORY_PAGE_SIZE,
            loyalty_point_id: 4,
        })
    })

    it('maps "all" to completed and cancelled', () => {
        expect(loyalty_history_query({ page: 1, status: 'all' }, 4)).toMatchObject({
            status: 'completed,cancelled',
            offset: 0,
            loyalty_point_id: 4,
        })
    })
})

describe('loyalty_history_partial_params', () => {
    it('omits defaults', () => {
        expect(loyalty_history_partial_params({ page: 1, status: 'completed' })).toEqual({})
    })

    it('includes non-default filters', () => {
        expect(loyalty_history_partial_params({ page: 2, status: 'cancelled' })).toEqual({
            page: '2',
            status: 'cancelled',
        })
    })
})
