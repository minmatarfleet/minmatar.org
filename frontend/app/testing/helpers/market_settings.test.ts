import { describe, expect, it } from 'vitest'
import {
    freight_in_view,
    isk_input_text,
    loyalty_in_view,
    loyalty_orders_key,
    parse_isk,
    percent_to_share,
    share_to_percent,
} from '@helpers/market_settings'

describe('parse_isk', () => {
    it('reads short and long amounts', () => {
        expect(parse_isk('95m')).toBe(95_000_000)
        expect(parse_isk('5B')).toBe(5_000_000_000)
        expect(parse_isk('1.25b')).toBe(1_250_000_000)
        expect(parse_isk('350,000')).toBe(350_000)
        expect(parse_isk('95 000 000')).toBe(95_000_000)
        expect(parse_isk('40M ISK')).toBe(40_000_000)
        expect(parse_isk('350k')).toBe(350_000)
        expect(parse_isk('.5m')).toBe(500_000)
    })

    it('is null when empty and NaN when not an amount', () => {
        expect(parse_isk('')).toBeNull()
        expect(parse_isk('  ')).toBeNull()
        expect(parse_isk(null)).toBeNull()
        expect(parse_isk('lots')).toBeNaN()
        expect(parse_isk('5x')).toBeNaN()
        expect(parse_isk('-5m')).toBeNaN()
    })
})

describe('isk_input_text', () => {
    it('writes the short form a manager types back', () => {
        expect(isk_input_text(95_000_000)).toBe('95M')
        expect(isk_input_text(5_000_000_000)).toBe('5B')
        expect(isk_input_text(1_250_000)).toBe('1.25M')
        expect(isk_input_text(1_234_567)).toBe('1,234,567')
        expect(isk_input_text(350_000)).toBe('350,000')
        expect(isk_input_text(null)).toBe('')
    })

    it('round-trips through parse_isk', () => {
        for (const value of [95_000_000, 5_000_000_000, 1_234_567, 0, 40_500_000])
            expect(parse_isk(isk_input_text(value))).toBe(value)
    })
})

describe('percentages', () => {
    it('converts shares to boxes and back', () => {
        expect(share_to_percent(0.012)).toBe('1.2')
        expect(share_to_percent(0.85)).toBe('85')
        expect(percent_to_share('1.2')).toBe(0.012)
        expect(percent_to_share('85%')).toBe(0.85)
        expect(percent_to_share('0.125')).toBe(0.00125)
        expect(percent_to_share('')).toBeNull()
    })
})

describe('views', () => {
    const corp = (express: number | null, accounts: boolean[]) => ({
        express_isk_per_lp: express,
        accounts: accounts.map((is_active) => ({ is_active })),
    }) as any

    it('filters LP corps', () => {
        expect(loyalty_in_view('express', corp(900, []))).toBe(true)
        expect(loyalty_in_view('express', corp(null, []))).toBe(false)
        expect(loyalty_in_view('no_accounts', corp(null, [false]))).toBe(true)
        expect(loyalty_in_view('no_accounts', { ...corp(null, []), active_account_count: 2 })).toBe(false)
        expect(loyalty_in_view('all', corp(null, []))).toBe(true)
    })

    it('names the orders a desk takes', () => {
        expect(loyalty_orders_key({ allow_buy: true, allow_sell: true })).toBe('both')
        expect(loyalty_orders_key({ allow_buy: false, allow_sell: true })).toBe('sell')
        expect(loyalty_orders_key({ allow_buy: false, allow_sell: false })).toBe('none')
    })

    it('filters freight routes', () => {
        const route = (active: boolean, fee_never_applies: boolean) => ({ active, fee_never_applies }) as any
        expect(freight_in_view('live', route(true, false))).toBe(true)
        expect(freight_in_view('retired', route(true, false))).toBe(false)
        expect(freight_in_view('fee_never', route(true, true))).toBe(true)
        expect(freight_in_view('fee_never', route(true, false))).toBe(false)
    })
})
