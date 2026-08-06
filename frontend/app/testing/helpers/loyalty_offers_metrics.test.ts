import { describe, expect, it } from 'vitest'

import type { LoyaltyOffer } from '@dtypes/api.minmatar.org'
import {
    compute_loyalty_offers_metrics,
    offer_is_low_weekly_lp_volume,
    offer_lp_for_volume,
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
        expect(metrics.weekly_lp_volume).toBe(40_000)
        expect(metrics.monthly_lp_volume).toBe(80_000)
    })

    it('returns null average when no volume weight exists', () => {
        const metrics = compute_loyalty_offers_metrics(
            [offer({ volume_7d: null, volume_30d: null })],
            'sell',
        )
        expect(metrics.average_isk_per_lp).toBeNull()
        expect(metrics.weekly_lp_volume).toBe(0)
        expect(metrics.monthly_lp_volume).toBe(0)
    })
})
