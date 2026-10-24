import type {
    LoyaltyMarketOrder,
    LoyaltyOrderStatsWeek,
} from '@dtypes/api.minmatar.org'

/** Sell orders are posted in steps of this many LP, up to the max. */
export const SELL_LP_STEP = 100_000
export const MAX_SELL_LP = 2_500_000
/** The poster has this long after a claim to send LP before auto-cancel. */
export const SEND_LP_HOURS = 48

export type LoyaltyOrderStage = 'posted' | 'claimed' | 'lp_sent' | 'paid'
export const ORDER_STAGES: LoyaltyOrderStage[] = ['posted', 'claimed', 'lp_sent', 'paid']

/** How far along the four-step sale an order is (cancelled: posted). */
export function order_stage_index(order: Pick<LoyaltyMarketOrder, 'status'>): number {
    switch (order.status) {
        case 'claimed':
        case 'awaiting_lp':
            return 1
        case 'awaiting_isk':
            return 2
        case 'completed':
            return 3
        default:
            return 0
    }
}

type OrderPeople = Pick<
    LoyaltyMarketOrder,
    'side' | 'created_by_user_id' | 'claimed_by_user_id'
>

/** Who transfers the LP: the seller on sell orders, the claimer on buys. */
export function lp_sender_id(order: OrderPeople): number | null {
    return order.side === 'buy' ? order.claimed_by_user_id : order.created_by_user_id
}

/** Who pays the ISK: the claimer on sell orders, the poster on buys. */
export function isk_payer_id(order: OrderPeople): number | null {
    return order.side === 'buy' ? order.created_by_user_id : order.claimed_by_user_id
}

export type LoyaltyOwedStep = 'claim' | 'send_lp' | 'pay_isk' | null

/** The next step and whether ``user_id`` is the one who owes it. */
export function owed_step(
    order: OrderPeople & Pick<LoyaltyMarketOrder, 'status'>,
): LoyaltyOwedStep {
    if (order.status === 'open') return 'claim'
    if (order.status === 'claimed' || order.status === 'awaiting_lp') return 'send_lp'
    if (order.status === 'awaiting_isk') return 'pay_isk'
    return null
}

export function user_owes_step(
    order: OrderPeople & Pick<LoyaltyMarketOrder, 'status'>,
    user_id: number,
): boolean {
    if (!user_id) return false
    const step = owed_step(order)
    if (step === 'send_lp') return lp_sender_id(order) === user_id
    if (step === 'pay_isk') return isk_payer_id(order) === user_id
    return false
}

/** When the latest claim landed (the clock for sending LP), or null. */
export function last_claim_at(order: Pick<LoyaltyMarketOrder, 'claims'>): Date | null {
    const times = (order.claims ?? []).map((claim) => new Date(claim.created_at).getTime())
    return times.length ? new Date(Math.max(...times)) : null
}

/** Auto-cancel deadline while the seller owes LP on a sell order. */
export function send_lp_deadline(order: LoyaltyMarketOrder): Date | null {
    if (order.side === 'buy') return null
    if (order.status !== 'claimed' && order.status !== 'awaiting_lp') return null
    const claimed = last_claim_at(order)
    return claimed ? new Date(claimed.getTime() + SEND_LP_HOURS * 3_600_000) : null
}

export interface LoyaltyDestination {
    name: string
    corporation_id: number | null
}

/** Where the LP goes: the order's destination, else its first claim's. */
export function order_destination(order: LoyaltyMarketOrder): LoyaltyDestination | null {
    if (order.destination_character_name) {
        return {
            name: order.destination_character_name,
            corporation_id: order.destination_corporation_id ?? null,
        }
    }
    const claim = (order.claims ?? []).find((c) => c.destination_corporation_name)
    return claim
        ? {
            name: claim.destination_corporation_name,
            corporation_id: claim.destination_corporation_id ?? null,
        }
        : null
}

export interface LoyaltyConverter {
    user_id: number
    name: string
    character_id: number | null
}

/** The Conversion Team member on the order (latest claimer first). */
export function order_converter(order: LoyaltyMarketOrder): LoyaltyConverter | null {
    if (order.side === 'buy') {
        return order.created_by_user_id
            ? {
                user_id: order.created_by_user_id,
                name: order.created_by_name ?? '',
                character_id: order.created_by_character_id,
            }
            : null
    }
    const claim = [...(order.claims ?? [])].reverse().find((c) => c.claimed_by_user_id)
    if (claim && claim.claimed_by_user_id)
        return {
            user_id: claim.claimed_by_user_id,
            name: claim.claimed_by_name ?? '',
            character_id: claim.claimed_by_character_id,
        }
    return order.claimed_by_user_id
        ? {
            user_id: order.claimed_by_user_id,
            name: order.claimed_by_name ?? '',
            character_id: order.claimed_by_character_id,
        }
        : null
}

/** ISK the whole order pays out (partial claims don't change the total). */
export function order_payout(order: Pick<LoyaltyMarketOrder, 'quantity' | 'isk_per_lp'>): number {
    return order.quantity * order.isk_per_lp
}

/** Everyone who claimed part of a sell order, in claim order, once each. */
export function order_claimers(order: LoyaltyMarketOrder): LoyaltyConverter[] {
    const seen = new Map<number, LoyaltyConverter>()
    for (const claim of order.claims ?? []) {
        if (!claim.claimed_by_user_id || seen.has(claim.claimed_by_user_id)) continue
        seen.set(claim.claimed_by_user_id, {
            user_id: claim.claimed_by_user_id,
            name: claim.claimed_by_name ?? '',
            character_id: claim.claimed_by_character_id,
        })
    }
    if (seen.size === 0) {
        const converter = order_converter(order)
        return converter ? [converter] : []
    }
    return [...seen.values()]
}

/** True while some, but not all, of an open order has been claimed. */
export function is_partly_claimed(order: LoyaltyMarketOrder): boolean {
    return order.status === 'open'
        && (order.quantity_claimed ?? 0) > 0
        && (order.quantity_remaining ?? 0) > 0
}

/**
 * Show the first ``visible`` items, but every item when the one we must
 * show (e.g. a highlighted order) sits further down.
 */
export function initially_expanded<T>(items: T[], visible: number, must_show?: (item: T) => boolean): boolean {
    if (items.length <= visible) return true
    return must_show ? items.slice(visible).some(must_show) : false
}

/** The viewer's own active orders: the ones waiting on them first. */
export function sort_my_orders(orders: LoyaltyMarketOrder[], user_id: number): LoyaltyMarketOrder[] {
    return [...orders].sort((a, b) => {
        const a_move = user_owes_step(a, user_id) ? 0 : 1
        const b_move = user_owes_step(b, user_id) ? 0 : 1
        if (a_move !== b_move) return a_move - b_move
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })
}

export interface LoyaltyWeekBar {
    week_start: string
    lp: number
    /** Bar height as a percentage of the busiest week. */
    percent: number
    is_current: boolean
}

export function weekly_bars(weekly: LoyaltyOrderStatsWeek[] | undefined): LoyaltyWeekBar[] {
    const weeks = weekly ?? []
    const max = Math.max(0, ...weeks.map((w) => w.lp))
    return weeks.map((week, index) => ({
        ...week,
        percent: max > 0 ? Math.max(2, Math.round((week.lp / max) * 100)) : 2,
        is_current: index === weeks.length - 1,
    }))
}

export type LoyaltyLaneKey = 'claim' | 'send_lp' | 'pay_isk'

/** Active orders grouped by the step that is owed next. */
export function desk_lanes(orders: LoyaltyMarketOrder[]): Record<LoyaltyLaneKey, LoyaltyMarketOrder[]> {
    const lanes: Record<LoyaltyLaneKey, LoyaltyMarketOrder[]> = {
        claim: [],
        send_lp: [],
        pay_isk: [],
    }
    for (const order of orders) {
        const step = owed_step(order)
        if (step) lanes[step].push(order)
    }
    // Express orders first, soonest deadline first (they carry a 24h
    // promise); then the rest oldest first, the longest wait on top.
    const rank = (order: LoyaltyMarketOrder) => order.express_due_at
        ? [0, new Date(order.express_due_at).getTime()]
        : [1, new Date(order.created_at).getTime()]
    for (const lane of Object.values(lanes))
        lane.sort((a, b) => {
            const [a_group, a_time] = rank(a)
            const [b_group, b_time] = rank(b)
            return a_group - b_group || a_time - b_time
        })
    return lanes
}

