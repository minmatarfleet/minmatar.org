import { ISK_REPORT, ISK_REPORT_UNIT, format_compact } from '@helpers/numbers'

/** ISK short labels for report UI (1.25T, 186B, 16.80B, 17M, 31k). */
export function format_isk(value: number): string {
    return format_compact(value, ISK_REPORT)
}

/** Per-unit prices: millions as format_isk, then 31.3k, 950. */
export function format_unit_isk(value: number): string {
    return format_compact(value, ISK_REPORT_UNIT)
}

export function percent(part: number, total: number): number {
    return total === 0 ? 0 : Math.round((part / total) * 1000) / 10
}

/** "15 Aug" from an ISO date. */
export function day_label(date: string): string {
    const d = new Date(`${date}T00:00:00Z`)
    return `${d.getUTCDate()} ${d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })}`
}
