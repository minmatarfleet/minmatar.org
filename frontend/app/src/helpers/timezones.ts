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

// Each region's brackets are fixed in that region's own clock (backend/timezones/brackets.py),
// so their EVE hours move with daylight saving.
const REFERENCE_ZONES: Record<TimezoneRegion, string> = {
    US: 'America/New_York',
    EU: 'Europe/Berlin',
    AU: 'Australia/Sydney',
}
const PRIME_HOURS = [18, 23] as const
const LATE_HOURS = [23, 3] as const

// Minutes the zone is ahead of UTC at that moment.
function zone_offset_minutes(zone: string, at: Date): number {
    const parts = Object.fromEntries(
        new Intl.DateTimeFormat('en-US', {
            timeZone: zone, hourCycle: 'h23',
            year: 'numeric', month: 'numeric', day: 'numeric',
            hour: 'numeric', minute: 'numeric',
        }).formatToParts(at).map(part => [part.type, part.value])
    )
    const local = Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute)
    return Math.round((local - at.getTime()) / 60000)
}

function eve_clock_from_local(local_hour: number, offset_minutes: number): string {
    const minutes = (((local_hour * 60 - offset_minutes) % 1440) + 1440) % 1440
    return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}

// "17:00–22:00" for EUTZ in winter: the bracket's hours in EVE time on that date. Empty for an unknown code.
export function timezone_hours(code: string, at: Date = new Date()): string {
    const region = bracket_region(code)
    if (!region || !is_timezone_bracket(code))
        return ''
    const [start, end] = code.endsWith('+') ? LATE_HOURS : PRIME_HOURS
    const minute = new Date(Math.floor(at.getTime() / 60000) * 60000)
    const offset = zone_offset_minutes(REFERENCE_ZONES[region], minute)
    return `${eve_clock_from_local(start, offset)}–${eve_clock_from_local(end, offset)}`
}
