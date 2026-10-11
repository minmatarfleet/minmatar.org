/** ISK short labels for report UI (1.25T, 186B, 16.8M, 31.3k). */
export function format_isk(value: number): string {
    if (value >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)}T`
    if (value >= 100_000_000_000) return `${Math.round(value / 1_000_000_000)}B`
    if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(0)}M`
    return `${(value / 1_000).toFixed(0)}k`
}

export function format_unit_isk(value: number): string {
    if (value >= 1_000_000) return format_isk(value)
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}k`
    return `${Math.round(value)}`
}

export function percent(part: number, total: number): number {
    return total === 0 ? 0 : Math.round((part / total) * 1000) / 10
}

/** "15 Aug" from an ISO date. */
export function day_label(date: string): string {
    const d = new Date(`${date}T00:00:00Z`)
    return `${d.getUTCDate()} ${d.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' })}`
}
