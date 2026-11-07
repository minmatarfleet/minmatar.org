/**
 * ISK amounts typed the way pilots write them ("1.8m", "800k", "2b",
 * "1,500,000"), for number grids such as SRP amounts.
 */

const UNITS: { suffix: string, value: number }[] = [
    { suffix: 'B', value: 1_000_000_000 },
    { suffix: 'M', value: 1_000_000 },
    { suffix: 'k', value: 1_000 },
]

const MULTIPLIERS: Record<string, number> = { k: 1_000, m: 1_000_000, b: 1_000_000_000 }

/**
 * Whole ISK from "1.8m", "800k", "2B", "1,500,000" or "1 500 000 ISK".
 * Null when the text is not an amount (empty, negative, letters).
 */
export function parse_isk_shorthand(text: string | null | undefined): number | null {
    const cleaned = String(text ?? '')
        .trim()
        .toLowerCase()
        .replace(/isk$/, '')
        .replace(/[\s,_]/g, '')
    const match = cleaned.match(/^(\d+(?:\.\d+)?|\.\d+)([kmb])?$/)
    if (!match)
        return null
    const amount = Number(match[1]) * (match[2] ? MULTIPLIERS[match[2]] : 1)
    return Number.isFinite(amount) ? Math.round(amount) : null
}

/**
 * The shortest exact shorthand ("1.8M", "800k", "1,234,567"): it parses back
 * to the same number, so an untouched field never reads as a change.
 */
export function format_isk_shorthand(value: number, locale: string = 'en-US'): string {
    for (const unit of UNITS) {
        if (value < unit.value)
            continue
        const scaled = value / unit.value
        // "12345.678k" is exact but unreadable: a smaller unit must stay under 1000.
        if (scaled >= 1000 && unit !== UNITS[0])
            continue
        // Up to three decimals, and only when exact.
        if (Math.round(scaled * 1000) === scaled * 1000)
            return `${Number(scaled.toFixed(3))}${unit.suffix}`
    }
    return Math.round(value).toLocaleString(locale)
}
