import type {
    CorporationPrimeWindow,
    CorporationSummarySlice,
} from '@dtypes/api.minmatar.org'

export interface MixRow {
    key: string
    count: number
    percent: number
    // Bar width in percent; never 0 for a non-zero row so it stays visible.
    width: number
    // Index into the one cream lightness ramp shared by every mix card.
    shade: number
}

export interface HeatmapCell {
    level: 0 | 1 | 2 | 3 | 4
    people: number
}

export interface PrimeSpan {
    zone: CorporationPrimeWindow['zone']
    pilots: number
    // 1-based CSS grid columns over the 24 hour cells (hour h is column h + 1).
    column_start: number
    column_end: number
    // A window that crosses midnight draws a second span; only the first is labelled.
    labelled: boolean
}

// Largest-remainder rounding so a card's percentages add up to exactly 100.
export function percent_shares(counts: number[]): number[] {
    const total = counts.reduce((sum, count) => sum + count, 0)
    if (total <= 0)
        return counts.map(() => 0)
    const exact = counts.map((count) => (count / total) * 100)
    const floors = exact.map((value) => Math.floor(value))
    let leftover = 100 - floors.reduce((sum, value) => sum + value, 0)
    const order = exact
        .map((value, index) => ({ index, fraction: value - Math.floor(value) }))
        .sort((left, right) => right.fraction - left.fraction || left.index - right.index)
    for (const row of order) {
        if (leftover <= 0)
            break
        floors[row.index] += 1
        leftover -= 1
    }
    return floors
}

// Rows in the given key order, empty ones dropped, shaded by position.
export function mix_rows(
    slices: CorporationSummarySlice[] | undefined,
    order: readonly string[],
): MixRow[] {
    const by_key = new Map((slices ?? []).map((slice) => [slice.key, slice.count]))
    const present = order
        .map((key) => ({ key, count: by_key.get(key) ?? 0 }))
        .filter((row) => row.count > 0)
    const percents = percent_shares(present.map((row) => row.count))
    const total = present.reduce((sum, row) => sum + row.count, 0)
    return present.map((row, index) => ({
        ...row,
        percent: percents[index] ?? 0,
        width: total > 0 ? Math.max((row.count / total) * 100, 1) : 0,
        shade: Math.min(index, 3),
    }))
}

// Rows sorted largest first, so the headline is always the first row.
export function ranked_mix_rows(
    slices: CorporationSummarySlice[] | undefined,
    order: readonly string[],
): MixRow[] {
    const rows = mix_rows(slices, order)
    return rows
        .slice()
        .sort((left, right) => right.count - left.count || order.indexOf(left.key) - order.indexOf(right.key))
        .map((row, index) => ({ ...row, shade: Math.min(index, 3) }))
}

// Five steps relative to the busiest hour, so a small corp still shows its shape.
export function heatmap_cells(heatmap: number[][] | undefined): HeatmapCell[][] {
    const rows = heatmap && heatmap.length === 7 ? heatmap : Array.from({ length: 7 }, () => Array(24).fill(0))
    const peak = Math.max(0, ...rows.flat())
    return rows.map((row) => Array.from({ length: 24 }, (_, hour) => {
        const people = row[hour] ?? 0
        if (people <= 0 || peak <= 0)
            return { level: 0 as const, people }
        const share = people / peak
        const level = share > 0.75 ? 4 : share > 0.4 ? 3 : share > 0.15 ? 2 : 1
        return { level: level as HeatmapCell['level'], people }
    }))
}

export function prime_spans(windows: CorporationPrimeWindow[] | undefined): PrimeSpan[] {
    const spans: PrimeSpan[] = []
    for (const window of windows ?? []) {
        const base = { zone: window.zone, pilots: window.pilots }
        if (window.end_hour > window.start_hour) {
            spans.push({ ...base, column_start: window.start_hour + 1, column_end: window.end_hour + 1, labelled: true })
            continue
        }
        spans.push({ ...base, column_start: window.start_hour + 1, column_end: 25, labelled: true })
        if (window.end_hour > 0)
            spans.push({ ...base, column_start: 1, column_end: window.end_hour + 1, labelled: false })
    }
    return spans
}

export function busiest_hours(heatmap: number[][] | undefined): { day: number, hour: number } | null {
    let best: { day: number, hour: number, people: number } | null = null
    for (const [day, row] of (heatmap ?? []).entries()) {
        for (const [hour, people] of row.entries()) {
            if (people > 0 && (!best || people > best.people))
                best = { day, hour, people }
        }
    }
    return best ? { day: best.day, hour: best.hour } : null
}

// "1.6 years", "8 months", "3 weeks".
export function tenure_parts(days: number | null | undefined): { value: string, unit: 'years' | 'months' | 'weeks' } | null {
    if (days == null || days < 0)
        return null
    if (days >= 365)
        return { value: (Math.round((days / 365.25) * 10) / 10).toString(), unit: 'years' }
    if (days >= 60)
        return { value: Math.round(days / 30.44).toString(), unit: 'months' }
    return { value: Math.max(1, Math.round(days / 7)).toString(), unit: 'weeks' }
}

// "2026-08" -> "August 2026" in the page language.
export function month_label(month: string, lang = 'en'): string {
    const [year, number] = month.split('-').map((part) => Number.parseInt(part, 10))
    if (!year || !number)
        return month
    return new Date(Date.UTC(year, number - 1, 1)).toLocaleDateString(lang, {
        month: 'long',
        year: 'numeric',
        timeZone: 'UTC',
    })
}

export function short_date(iso: string | null | undefined, lang = 'en'): string {
    if (!iso)
        return ''
    const date = new Date(iso)
    if (Number.isNaN(date.getTime()))
        return ''
    return date.toLocaleDateString(lang, { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
}

export function month_year(iso: string | null | undefined, lang = 'en'): string {
    if (!iso)
        return ''
    const date = new Date(iso)
    if (Number.isNaN(date.getTime()))
        return ''
    return date.toLocaleDateString(lang, { month: 'short', year: 'numeric', timeZone: 'UTC' })
}

export function initials(name: string): string {
    return name
        .replace(/[^A-Za-z0-9 ]/g, ' ')
        .split(' ')
        .filter(Boolean)
        .map((word) => word[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
}
