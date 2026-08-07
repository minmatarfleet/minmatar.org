import { describe, expect, it } from 'vitest'

import type { LoyaltyOffer } from '@dtypes/api.minmatar.org'
import {
    STABLE_WEEKLY_CAPTURE_SHARE,
    compute_loyalty_offers_metrics,
    conversion_for_side,
    expand_useless_offer_excludes,
    offer_is_low_weekly_lp_volume,
    offer_lp_for_volume,
    sort_loyalty_offers,
    useless_offer_exclude_toggle,
} from '@helpers/loyalty_offers_metrics'

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

describe('offer_lp_for_volume', () => {
    it('ceil-packs volume into LP cost', () => {
        expect(offer_lp_for_volume(offer({ quantity: 3, lp_cost: 1000 }), 10))
            .toBe(4000)
    })

    it('returns 0 for missing volume', () => {
        expect(offer_lp_for_volume(offer({}), null)).toBe(0)
    })
})

describe('offer_is_low_weekly_lp_volume', () => {
    it('flags offers under 1M weekly LP', () => {
        expect(offer_is_low_weekly_lp_volume(offer({
            lp_cost: 100_000,
            quantity: 1,
            volume_7d: 9,
        }))).toBe(true)
    })

    it('does not flag offers at or above 1M weekly LP', () => {
        expect(offer_is_low_weekly_lp_volume(offer({
            lp_cost: 100_000,
            quantity: 1,
            volume_7d: 10,
        }))).toBe(false)
    })

    it('flags missing volume as low', () => {
        expect(offer_is_low_weekly_lp_volume(offer({ volume_7d: null })))
            .toBe(true)
    })
})

describe('compute_loyalty_offers_metrics', () => {
    it('weights average ISK/LP by weekly LP volume for the active side', () => {
        const metrics = compute_loyalty_offers_metrics(
            [
                offer({
                    conversion_isk_per_lp_buy: 1000,
                    volume_7d: 10,
                    lp_cost: 1000,
                    quantity: 1,
                }),
                offer({
                    offer_id: 2,
                    conversion_isk_per_lp_buy: 500,
                    volume_7d: 30,
                    lp_cost: 1000,
                    quantity: 1,
                }),
            ],
            'buy',
        )
        // weights 10k and 30k LP → (1000*10k + 500*30k) / 40k = 625
        expect(metrics.average_isk_per_lp).toBe(625)
        expect(metrics.weekly_total_volume).toBe(40_000)
        expect(metrics.weekly_stable_volume)
            .toBe(40_000 * STABLE_WEEKLY_CAPTURE_SHARE)
    })

    it('returns null average when no volume weight exists', () => {
        const metrics = compute_loyalty_offers_metrics(
            [offer({ volume_7d: null, volume_30d: null })],
            'sell',
        )
        expect(metrics.average_isk_per_lp).toBeNull()
        expect(metrics.weekly_total_volume).toBe(0)
        expect(metrics.weekly_stable_volume).toBe(0)
    })

    it('adds freight back into the average when freight is excluded', () => {
        const metrics = compute_loyalty_offers_metrics(
            [
                offer({
                    lp_cost: 100_000,
                    quantity: 1,
                    jita_buy: 200_000_000,
                    input_cost_isk: 50_000_000,
                    input_freight_isk: 1_500_000,
                    conversion_isk_per_lp_buy: 1200,
                    volume_7d: 10,
                }),
            ],
            'buy',
            false,
        )
        // 1200 + 15 input freight + 60 output freight
        expect(metrics.average_isk_per_lp).toBe(1275)
    })
})

describe('conversion_for_side', () => {
    it('returns API net when freight is included', () => {
        expect(conversion_for_side(
            offer({ conversion_isk_per_lp_buy: 1200 }),
            'buy',
            true,
        )).toBe(1200)
    })

    it('adds freight when excluded', () => {
        expect(conversion_for_side(
            offer({
                lp_cost: 100_000,
                jita_buy: 200_000_000,
                input_freight_isk: 1_500_000,
                conversion_isk_per_lp_buy: 1200,
            }),
            'buy',
            false,
        )).toBe(1275)
    })

    it('adds sales tax when excluded', () => {
        expect(conversion_for_side(
            offer({
                lp_cost: 100_000,
                jita_buy: 200_000_000,
                input_freight_isk: 0,
                conversion_isk_per_lp_buy: 1200,
            }),
            'buy',
            true,
            false,
        )).toBeCloseTo(1267.4, 5)
    })
})

describe('sort_loyalty_offers', () => {
    it('re-sorts by conversion without freight when freight is excluded', () => {
        const high_freight = offer({
            offer_id: 1,
            lp_cost: 100_000,
            jita_buy: 100_000_000,
            input_freight_isk: 17_000_000,
            conversion_isk_per_lp_buy: 900,
            // without freight: 900 + 170 input + 30 output = 1100
        })
        const low_freight = offer({
            offer_id: 2,
            lp_cost: 100_000,
            jita_buy: 100_000_000,
            input_freight_isk: 0,
            conversion_isk_per_lp_buy: 1000,
            // without freight: 1000 + 30 output = 1030
        })
        // API order by freight-inclusive buy conversion: 1000 then 900
        const api_order = [low_freight, high_freight]
        expect(sort_loyalty_offers(
            api_order,
            '-conversion_buy',
            'buy',
            true,
        ).map((o) => o.offer_id)).toEqual([2, 1])
        expect(sort_loyalty_offers(
            api_order,
            '-conversion_buy',
            'buy',
            false,
        ).map((o) => o.offer_id)).toEqual([1, 2])
    })
})

describe('expand_useless_offer_excludes', () => {
    it('bundles packages, chips, and skins when useless is on', () => {
        expect(expand_useless_offer_excludes('1')).toEqual({
            exclude_useless_offers: '1',
            exclude_supply_packages: '1',
            exclude_chips: '1',
            exclude_skins: '1',
        })
    })

    it('returns empty when useless is off', () => {
        expect(expand_useless_offer_excludes(undefined)).toEqual({})
        expect(expand_useless_offer_excludes('0')).toEqual({})
    })
})

describe('useless_offer_exclude_toggle', () => {
    it('clears the full bundle when disabling', () => {
        expect(useless_offer_exclude_toggle(false)).toEqual({
            exclude_useless_offers: undefined,
            exclude_supply_packages: undefined,
            exclude_chips: undefined,
            exclude_skins: undefined,
        })
    })
})
