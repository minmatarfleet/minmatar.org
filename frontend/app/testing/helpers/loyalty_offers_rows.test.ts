import { describe, expect, it } from 'vitest'

import type { LoyaltyOffer } from '@dtypes/api.minmatar.org'
import {
    api_offer_ordering,
    bar_percent,
    format_short_amount,
    net_bar_scale,
    offer_capital_per_100k_lp,
    offer_depth,
    offer_lp_waterfall,
    offer_recipe,
    offer_row_figures,
    offer_weekly_lp,
    parse_required_items,
    sort_offers_by_local_key,
    summarize_deep_offers,
} from '@helpers/loyalty_offers_rows'

function offer(overrides: Partial<LoyaltyOffer>): LoyaltyOffer {
    return {
        offer_id: 1,
        corporation_id: 1000182,
        type_id: 1,
        type_name: 'Test',
        currency_name: 'TLIB',
        lp_cost: 1000,
        isk_cost: 0,
        ak_cost: 0,
        quantity: 1,
        required_items_summary: '',
        other_cost: null,
        input_cost_isk: null,
        input_freight_isk: null,
        jita_sell: null,
        jita_buy: null,
        jita_avg_7d: null,
        conversion_isk_per_lp_sell: 1000,
        conversion_isk_per_lp_buy: 900,
        conversion_isk_per_lp_avg_7d: 950,
        volume_1d: null,
        volume_7d: 10,
        volume_30d: 40,
        kind: 'input',
        updated_at: '2026-08-05T00:00:00Z',
        ...overrides,
    }
}

/** Live numbers for Navy Cap Booster 400 ×20 (Oct 2026). */
const cap_booster = offer({
    type_name: 'Navy Cap Booster 400',
    lp_cost: 1000,
    isk_cost: 1_000_000,
    quantity: 20,
    required_items_summary: 'Cap Booster 400 x20',
    other_cost: 129_920,
    input_cost_isk: 1_129_920,
    input_freight_isk: 3898,
    jita_buy: 100_800,
    conversion_isk_per_lp_buy: 753.762,
    volume_7d: 298_642,
})

describe('offer_capital_per_100k_lp', () => {
    it('quotes store ISK + required items per 100K LP', () => {
        expect(offer_capital_per_100k_lp(cap_booster)).toBeCloseTo(112_992_000)
    })

    it('falls back to isk_cost + other_cost', () => {
        expect(offer_capital_per_100k_lp(offer({
            isk_cost: 500_000,
            other_cost: 100_000,
        }))).toBeCloseTo(60_000_000)
    })

    it('is null without an LP cost', () => {
        expect(offer_capital_per_100k_lp(offer({ lp_cost: 0 }))).toBeNull()
    })
})

describe('offer_weekly_lp + offer_depth', () => {
    it('converts 7d units into LP', () => {
        expect(offer_weekly_lp(cap_booster)).toBe(14_933_000)
        expect(format_short_amount(offer_weekly_lp(cap_booster))).toBe('14.9M')
    })

    it('buckets by weekly LP', () => {
        expect(offer_depth(499_999)).toBe('thin')
        expect(offer_depth(500_000)).toBe('steady')
        expect(offer_depth(5_000_000)).toBe('steady')
        expect(offer_depth(5_000_001)).toBe('deep')
    })
})

describe('format_short_amount', () => {
    it('shortens large values', () => {
        expect(format_short_amount(112_992_000)).toBe('113M')
        expect(format_short_amount(1_250_000_000)).toBe('1.3B')
        expect(format_short_amount(600_000)).toBe('600K')
        expect(format_short_amount(50_480_000)).toBe('50.5M')
        expect(format_short_amount(999_960)).toBe('1M')
        expect(format_short_amount(950)).toBe('950')
        expect(format_short_amount(0)).toBe('0')
        expect(format_short_amount(null)).toBe('—')
    })
})

describe('parse_required_items / offer_recipe', () => {
    it('parses names and quantities', () => {
        expect(parse_required_items('Cap Booster 400 x20, Social Adaptation Chip - Basic x1'))
            .toEqual([
                { name: 'Cap Booster 400', quantity: 20 },
                { name: 'Social Adaptation Chip - Basic', quantity: 1 },
            ])
        expect(parse_required_items('')).toEqual([])
    })

    it('hides required quantity when it pairs with the offer quantity', () => {
        const recipe = offer_recipe(cap_booster)
        expect(recipe.lp_cost).toBe(1000)
        expect(recipe.isk_cost).toBe(1_000_000)
        expect(recipe.items).toEqual([
            { name: 'Cap Booster 400', quantity: 20, show_quantity: false },
        ])
        expect(offer_recipe(offer({ quantity: 1, required_items_summary: 'Bouncer I x5' })).items[0].show_quantity)
            .toBe(true)
    })
})

describe('net_bar_scale + bar_percent', () => {
    it('scales to the best net within 1.25–2× the buyback', () => {
        expect(net_bar_scale([754, 811], 700)).toBe(875)
        expect(net_bar_scale([1000], 700)).toBe(1000)
        expect(net_bar_scale([2500], 700)).toBe(1400)
        expect(net_bar_scale([300, null], null)).toBe(300)
        expect(net_bar_scale([], null)).toBe(1)
    })

    it('clamps widths to 0–100', () => {
        expect(bar_percent(700, 875)).toBeCloseTo(80)
        expect(bar_percent(2000, 875)).toBe(100)
        expect(bar_percent(-50, 875)).toBe(0)
        expect(bar_percent(null, 875)).toBe(0)
    })
})

describe('summarize_deep_offers', () => {
    it('takes net and capital ranges from deep rows only', () => {
        const summary = summarize_deep_offers([
            { net_isk_per_lp: 754, capital_per_100k_lp: 113e6, weekly_lp: 14e6, depth: 'deep' },
            { net_isk_per_lp: 740, capital_per_100k_lp: 128e6, weekly_lp: 9e6, depth: 'deep' },
            { net_isk_per_lp: 1280, capital_per_100k_lp: 117e6, weekly_lp: 1e5, depth: 'thin' },
        ])
        expect(summary).toEqual({
            count: 2,
            net_min: 740,
            net_max: 754,
            capital_min: 113e6,
            capital_max: 128e6,
        })
    })

    it('is empty without deep rows', () => {
        expect(summarize_deep_offers([]).net_min).toBeNull()
    })
})

describe('offer_row_figures', () => {
    it('matches the cap booster sanity numbers', () => {
        const row = offer_row_figures(cap_booster, 'buy', true, true)
        expect(row.net_isk_per_lp).toBeCloseTo(753.762)
        expect(row.depth).toBe('deep')
    })
})

describe('local orderings', () => {
    const a = offer({ offer_id: 1, isk_cost: 100_000, volume_7d: 10 })
    const b = offer({ offer_id: 2, isk_cost: 900_000, volume_7d: 5 })

    it('sorts by capital and weekly LP', () => {
        expect(sort_offers_by_local_key([a, b], '-capital_per_100k').map((o) => o.offer_id))
            .toEqual([2, 1])
        expect(sort_offers_by_local_key([b, a], 'weekly_lp').map((o) => o.offer_id))
            .toEqual([2, 1])
    })

    it('passes API orderings through', () => {
        const offers = [b, a]
        expect(sort_offers_by_local_key(offers, '-conversion_buy')).toBe(offers)
        expect(api_offer_ordering('-conversion_buy', 'buy')).toBe('-conversion_buy')
        expect(api_offer_ordering('-weekly_lp', 'sell')).toBe('-conversion_sell')
    })
})

describe('offer_lp_waterfall', () => {
    it('walks gross Jita value down to net', () => {
        const fall = offer_lp_waterfall(cap_booster, 'buy', {
            include_freight: true,
            include_sales_tax: true,
        })
        expect(fall.gross_isk_per_lp).toBeCloseTo(2016)
        expect(fall.costs.map((c) => c.key)).toEqual([
            'store_isk',
            'required_items',
            'freight_in',
            'sales_tax',
            'freight_out',
        ])
        expect(fall.costs[0].isk_per_lp).toBeCloseTo(1000)
        expect(fall.costs[1].isk_per_lp).toBeCloseTo(129.92)
        const sum = fall.costs.reduce((total, c) => total + c.isk_per_lp, 0)
        expect((fall.gross_isk_per_lp ?? 0) - sum).toBeCloseTo(fall.net_isk_per_lp ?? 0, 1)
    })

    it('drops costs switched off and adds them back into net', () => {
        const fall = offer_lp_waterfall(cap_booster, 'buy', {
            include_freight: false,
            include_sales_tax: false,
        })
        expect(fall.costs.map((c) => c.key)).toEqual(['store_isk', 'required_items'])
        expect(fall.net_isk_per_lp).toBeCloseTo(2016 - 1000 - 129.92, 0)
    })
})
