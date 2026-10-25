// Pilot timezone brackets as the timezones app defines them (backend/timezones/brackets.py).
export const TIMEZONE_BRACKETS = ['USTZ', 'USTZ+', 'EUTZ', 'EUTZ+', 'AUTZ', 'AUTZ+'] as const

export type TimezoneBracket = typeof TIMEZONE_BRACKETS[number]

export function is_timezone_bracket(code: string): code is TimezoneBracket {
    return (TIMEZONE_BRACKETS as readonly string[]).includes(code)
}

// "US evening" for USTZ; an unknown code is shown as it is.
export function timezone_description(code: string, t: (key: any) => string): string {
    return is_timezone_bracket(code) ? t(`timezones.${code}`) : code
}

// The three regions a bracket belongs to: USTZ and USTZ+ are US, and so on.
export const TIMEZONE_REGIONS = ['US', 'EU', 'AU'] as const
export type TimezoneRegion = typeof TIMEZONE_REGIONS[number]

type TagLike = { brackets?: string[] | null } | null | undefined

export function bracket_region(code: string): TimezoneRegion | null {
    return TIMEZONE_REGIONS.find(region => code.startsWith(`${region}TZ`)) ?? null
}

// Regions a pilot plays in, in bracket order (US, EU, AU), each once.
export function timezone_regions(timezone: TagLike): TimezoneRegion[] {
    const present = new Set((timezone?.brackets ?? []).map(bracket_region))
    return TIMEZONE_REGIONS.filter(region => present.has(region))
}

// Sort rank: the earliest bracket a pilot holds (USTZ first); none sorts last.
export function timezone_rank(timezone: TagLike): number {
    const ranks = (timezone?.brackets ?? [])
        .map(code => (TIMEZONE_BRACKETS as readonly string[]).indexOf(code))
        .map(index => index < 0 ? TIMEZONE_BRACKETS.length : index)
    return ranks.length > 0 ? Math.min(...ranks) : TIMEZONE_BRACKETS.length + 1
}

// Roster filters: a base bracket also matches its + bracket; 'none' is No TZ yet.
export const TIMEZONE_FILTERS = ['USTZ', 'EUTZ', 'AUTZ', 'none'] as const
export type TimezoneFilter = typeof TIMEZONE_FILTERS[number]

export function timezone_matches(timezone: TagLike, filter: TimezoneFilter): boolean {
    const brackets = timezone?.brackets ?? []
    if (filter === 'none')
        return brackets.length === 0
    return brackets.some(code => code === filter || code === `${filter}+`)
}
