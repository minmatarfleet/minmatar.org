export type BuybackRateReason = 'supply_chain_import' | 'accepted_surplus'

export interface BuybackRateBadgeView {
    reason: BuybackRateReason
    text_key: 'buyback.info.in_demand' | 'buyback.info.surplus'
    tip_key: 'buyback.info.in_demand_tip' | 'buyback.info.surplus_tip'
    class_name: 'buyback-rate--demand' | 'buyback-rate--surplus'
}

export function buyback_rate_badge(
    rate_reason: string | null | undefined,
): BuybackRateBadgeView | null {
    if (rate_reason === 'supply_chain_import') {
        return {
            reason: 'supply_chain_import',
            text_key: 'buyback.info.in_demand',
            tip_key: 'buyback.info.in_demand_tip',
            class_name: 'buyback-rate--demand',
        }
    }
    if (rate_reason === 'accepted_surplus') {
        return {
            reason: 'accepted_surplus',
            text_key: 'buyback.info.surplus',
            tip_key: 'buyback.info.surplus_tip',
            class_name: 'buyback-rate--surplus',
        }
    }
    return null
}

export function buyback_rate_badge_from_in_demand(
    in_demand: boolean,
): BuybackRateBadgeView {
    return buyback_rate_badge(
        in_demand ? 'supply_chain_import' : 'accepted_surplus',
    ) as BuybackRateBadgeView
}
