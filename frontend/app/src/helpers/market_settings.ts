/**
 * Helpers for the market settings screens: LP desk settings, freight routes
 * and buyback settings (pages/partials/{loyalty,freight_routes,buyback}_settings_component).
 */
import type {
    BuybackManageItem,
    BuybackManageSettings,
    FreightManageRoute,
    LoyaltySettingsCurrency,
} from '@dtypes/api.minmatar.org'

// Fields the backend added for these screens. The generated schema gains them
// when openapi.json and api.d.ts are regenerated; until then they are optional
// here. After the regeneration these intersections are no-ops.
export type LoyaltyPriceChange = {
    tier: string
    account_name: string | null
    old_isk_per_lp: number | null
    new_isk_per_lp: number | null
    changed_at: string
    changed_by: string | null
}

export type LoyaltyDeskCorp = LoyaltySettingsCurrency & {
    active_account_count?: number
    last_change?: LoyaltyPriceChange | null
}

export type FreightRouteQuote = {
    m3: number
    collateral: number
    cost: number
    fee_never_applies: boolean
}

export type FreightEditorRoute = FreightManageRoute & {
    fee_never_applies?: boolean
    quote?: FreightRouteQuote | null
}

export type BuybackEditorItem = BuybackManageItem & {
    category_label?: string
    demand_status?: string
    demand_label?: string
    pays_rate?: number | null
}

export type BuybackEditorSettings = Omit<BuybackManageSettings, 'items'> & {
    location_name?: string | null
    items: BuybackEditorItem[]
}

const ISK_SUFFIXES: Record<string, number> = {
    '': 1,
    k: 1e3,
    m: 1e6,
    b: 1e9,
    t: 1e12,
}

/**
 * Read an ISK amount as typed: "95m", "5b", "1.5B", "350,000", "95 000 000",
 * "40M ISK". Returns null for an empty box and NaN for text that is not an
 * amount. The result is whole ISK.
 */
export function parse_isk(text: string | null | undefined): number | null {
    const cleaned = String(text ?? '')
        .trim()
        .toLowerCase()
        .replace(/isk$/, '')
        .replace(/[\s,_]/g, '')
    if (cleaned === '')
        return null
    const match = cleaned.match(/^(\d+(?:\.\d+)?|\.\d+)([kmbt]?)$/)
    if (!match)
        return NaN
    return Math.round(parseFloat(match[1]) * ISK_SUFFIXES[match[2]])
}

/**
 * An ISK amount for an input box, in the short form a manager types back:
 * 95000000 -> "95M", 5000000000 -> "5B", 1250000 -> "1.25M". Amounts that do
 * not fit two decimals of a unit keep every digit ("1,234,567").
 */
export function isk_input_text(value: number | null | undefined): string {
    if (value == null || !Number.isFinite(value))
        return ''
    for (const [suffix, divisor] of [['T', 1e12], ['B', 1e9], ['M', 1e6]] as const) {
        if (Math.abs(value) < divisor)
            continue
        const units = value / divisor
        if (Math.abs(Math.round(units * 100) - units * 100) < 1e-6)
            return `${Number(units.toFixed(2))}${suffix}`
    }
    return Math.round(value).toLocaleString('en-US')
}

/** LP desk table: corporation, standard, express, accounts, desk open, chevron. */
export const LP_DESK_COLSPAN = 6

/** Freight routes table: route, price, limits, days, live, chevron. */
export const FREIGHT_COLSPAN = 6

/** LP desk views: all, express on, and the "no accounts" attention chip. */
export type LoyaltyDeskView = 'all' | 'express' | 'no_accounts'

export function loyalty_active_accounts(corp: LoyaltyDeskCorp): number {
    return corp.active_account_count ?? corp.accounts.filter((account) => account.is_active).length
}

export function loyalty_in_view(view: string, corp: LoyaltyDeskCorp): boolean {
    if (view === 'express')
        return corp.express_isk_per_lp !== null
    if (view === 'no_accounts')
        return loyalty_active_accounts(corp) === 0
    return true
}

/** Which orders a desk takes: both, one side, or none. */
export function loyalty_orders_key(corp: { allow_buy: boolean, allow_sell: boolean }): 'both' | 'buy' | 'sell' | 'none' {
    if (corp.allow_buy && corp.allow_sell)
        return 'both'
    if (corp.allow_buy)
        return 'buy'
    if (corp.allow_sell)
        return 'sell'
    return 'none'
}

/** Freight views: all, live, retired, and the "fee never applies" chip. */
export function freight_in_view(view: string, route: FreightEditorRoute): boolean {
    if (view === 'live')
        return route.active
    if (view === 'retired')
        return !route.active
    if (view === 'fee_never')
        return route.fee_never_applies === true
    return true
}

/** Share (0-1) to a percentage box value: 0.012 -> "1.2". */
export function share_to_percent(share: number | null | undefined): string {
    if (share == null || !Number.isFinite(share))
        return ''
    return String(Number((share * 100).toFixed(2)))
}

/** Percentage box value to a share: "1.2" -> 0.012; empty or junk -> null. */
export function percent_to_share(text: string | null | undefined): number | null {
    const value = parseFloat(String(text ?? '').replace('%', '').trim())
    return Number.isFinite(value) ? Math.round(value * 1e4) / 1e6 : null
}

/** Buyback item views: all, or one category ("ore", "p1"). */
export function buyback_in_view(view: string, item: BuybackEditorItem): boolean {
    return view === 'all' || item.category === view
}
