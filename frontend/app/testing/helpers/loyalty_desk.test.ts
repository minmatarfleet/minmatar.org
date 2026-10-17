import { describe, expect, it } from 'vitest'

import type { LoyaltyMarketOrder } from '@dtypes/api.minmatar.org'
import {
    clamp_sell_amount,
    desk_lanes,
    order_converter,
    order_destination,
    order_payout,
    order_stage_index,
    send_lp_deadline,
    user_owes_step,
    weekly_bars,
} from '@helpers/loyalty_desk'

const SELLER = 10
const CONVERTER = 20

function order(overrides: Partial<LoyaltyMarketOrder>): LoyaltyMarketOrder {
    return {
        id: 1,
        loyalty_point_id: 1,
        loyalty_point_name: 'Tribal Liberation Force',
        corporation_id: 1000182,
        side: 'sell',
        quantity: 700_000,
        quantity_claimed: 0,
        quantity_remaining: 700_000,
        isk_per_lp: 700,
        tier: 'standard',
        express_due_at: null,
        status: 'open',
        created_by_user_id: SELLER,
        created_by_name: 'Seller',
        created_by_character_id: 1,
        claimed_by_user_id: null,
        claimed_by_name: null,
        claimed_by_character_id: null,
        destination_character_name: '',
        discord_thread_id: null,
        notes: '',
        claims: [],
        created_at: '2026-10-17T00:42:00Z',
        updated_at: '2026-10-17T00:42:00Z',
        completed_at: null,
        ...overrides,
    }
}

const claimed = order({
    status: 'awaiting_lp',
    quantity_claimed: 700_000,
    quantity_remaining: 0,
    claimed_by_user_id: CONVERTER,
    claimed_by_name: 'Kayra Nathuul',
    claimed_by_character_id: 93389269,
    destination_character_name: 'Lastas Trade Corporation',
    destination_corporation_id: 98487524,
    claims: [{
        id: 1,
        amount: 700_000,
        destination_character_name: '',
        destination_corporation_name: 'Lastas Trade Corporation',
        destination_corporation_id: 98487524,
        claimed_by_user_id: CONVERTER,
        claimed_by_name: 'Kayra Nathuul',
        claimed_by_character_id: 93389269,
        created_at: '2026-10-17T12:33:00Z',
    }],
})

describe('loyalty desk helpers', () => {
    it('maps statuses onto the four-step sale', () => {
        expect(order_stage_index(order({ status: 'open' }))).toBe(0)
        expect(order_stage_index(claimed)).toBe(1)
        expect(order_stage_index(order({ status: 'awaiting_isk' }))).toBe(2)
        expect(order_stage_index(order({ status: 'completed' }))).toBe(3)
    })

    it('knows who owes the next step on sell and buy orders', () => {
        expect(user_owes_step(claimed, SELLER)).toBe(true)
        expect(user_owes_step(claimed, CONVERTER)).toBe(false)
        const paying = { ...claimed, status: 'awaiting_isk' }
        expect(user_owes_step(paying, CONVERTER)).toBe(true)
        expect(user_owes_step(paying, SELLER)).toBe(false)
        // On a buy order the claimer sends LP and the poster pays.
        const buy = { ...claimed, side: 'buy' }
        expect(user_owes_step(buy, CONVERTER)).toBe(true)
        expect(user_owes_step(buy, 0)).toBe(false)
    })

    it('gives the seller 48 hours from the claim to send LP', () => {
        expect(send_lp_deadline(claimed)?.toISOString()).toBe('2026-10-19T12:33:00.000Z')
        expect(send_lp_deadline(order({ status: 'open' }))).toBeNull()
        expect(send_lp_deadline({ ...claimed, status: 'awaiting_isk' })).toBeNull()
    })

    it('reads destination, converter and payout', () => {
        expect(order_destination(claimed)).toEqual({
            name: 'Lastas Trade Corporation',
            corporation_id: 98487524,
        })
        expect(order_destination(order({}))).toBeNull()
        expect(order_converter(claimed)?.character_id).toBe(93389269)
        expect(order_converter(order({}))).toBeNull()
        expect(order_payout(claimed)).toBe(490_000_000)
    })

    it('scales weekly bars to the busiest week', () => {
        const bars = weekly_bars([
            { week_start: '2026-10-05', lp: 20_000_000 },
            { week_start: '2026-10-12', lp: 5_000_000 },
        ])
        expect(bars.map((b) => b.percent)).toEqual([100, 25])
        expect(bars[1].is_current).toBe(true)
        expect(weekly_bars(undefined)).toEqual([])
    })

    it('groups active orders into desk lanes, oldest first', () => {
        const newer = order({ id: 2, created_at: '2026-10-17T05:00:00Z' })
        const older = order({ id: 3, created_at: '2026-10-10T05:00:00Z' })
        const lanes = desk_lanes([newer, claimed, older, order({ id: 4, status: 'completed' })])
        expect(lanes.claim.map((o) => o.id)).toEqual([3, 2])
        expect(lanes.send_lp.map((o) => o.id)).toEqual([1])
        expect(lanes.pay_isk).toEqual([])
    })

    it('clamps sell amounts to 100K steps within the order limits', () => {
        expect(clamp_sell_amount(0)).toBe(100_000)
        expect(clamp_sell_amount(1_040_000)).toBe(1_000_000)
        expect(clamp_sell_amount(9_000_000)).toBe(2_500_000)
    })
})
