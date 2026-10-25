import { describe, expect, it } from 'vitest'
import type { OrderLinePricing } from '@dtypes/api.minmatar.org'
import { parse_margin, parse_price_basis, preset_available, resolve_line_price } from '@helpers/order_pricing'

const pricing = (overrides: Partial<OrderLinePricing> = {}): OrderLinePricing => ({
    type_id: 644,
    quantity: 10,
    build_cost_per_unit: 137_500_000,
    jita_buy: 138_100_000,
    jita_split: 146_550_000,
    jita_sell: 155_000_000,
    ship_in_per_unit: 22_500_000,
    jita_delivered: 177_500_000,
    ...overrides,
})

describe('resolve_line_price', () => {
    it('uses a preset above the build cost', () => {
        const line = resolve_line_price(pricing(), 'jita_split', 5)
        expect(line).toEqual({ basis: 'jita_split', margin: 6.6, price: 146_550_000, profit: 9_050_000, saving: 30_950_000 })
    })

    it('holds a preset below the build cost at the build cost', () => {
        const priced = pricing({ build_cost_per_unit: 138_300_000 })
        expect(preset_available(priced, 'jita_buy')).toBe(false)
        const line = resolve_line_price(priced, 'jita_buy', 5)
        expect(line.basis).toBe('margin')
        expect(line.margin).toBe(0)
        expect(line.price).toBe(138_300_000)
    })

    it('never goes below the build cost on a negative margin', () => {
        expect(resolve_line_price(pricing(), 'margin', -3).price).toBe(137_500_000)
    })

    it('flags a price above Jita delivered with a negative saving', () => {
        const line = resolve_line_price(pricing(), 'margin', 30)
        expect(line.price).toBe(178_750_000)
        expect(line.saving).toBe(-1_250_000)
    })

    it('has no saving without a Jita price', () => {
        expect(resolve_line_price(pricing({ jita_delivered: null }), 'margin', 5).saving).toBeNull()
    })
})

describe('parsing form values', () => {
    it('defaults unknown bases to split and blank margins to 5%', () => {
        expect(parse_price_basis('nope')).toBe('jita_split')
        expect(parse_price_basis('jita_sell')).toBe('jita_sell')
        expect(parse_margin('')).toBe(5)
        expect(parse_margin('12.5')).toBe(12.5)
    })
})
