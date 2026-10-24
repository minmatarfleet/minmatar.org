import type { LoyaltyCurrency } from '@dtypes/api.minmatar.org'
import { TLIB_CORP_ID } from '@helpers/loyalty_offers_metrics'

/** Express orders promise settlement within this many hours of posting. */
export const EXPRESS_SLA_HOURS = 24

/** The TLF currency row (the only LP the buyback book trades), or null. */
export function tlf_currency(currencies: LoyaltyCurrency[]): LoyaltyCurrency | null {
    return currencies.find((c) => c.corporation_id === TLIB_CORP_ID) ?? null
}

/** Compact duration: "45m", "14h 20m", "2d 6h". */
export function format_close_time(seconds: number | null | undefined): string {
    if (seconds == null || !Number.isFinite(seconds)) return '—'
    const minutes = Math.max(0, Math.round(seconds / 60))
    if (minutes < 60) return `${minutes}m`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) {
        const rem = minutes % 60
        return rem ? `${hours}h ${rem}m` : `${hours}h`
    }
    const days = Math.floor(hours / 24)
    const rem = hours % 24
    return rem ? `${days}d ${rem}h` : `${days}d`
}

/** Hours left until an express deadline (negative when overdue). */
export function express_hours_left(due_at: Date | string, now: Date = new Date()): number {
    return (new Date(due_at).getTime() - now.getTime()) / 3_600_000
}
