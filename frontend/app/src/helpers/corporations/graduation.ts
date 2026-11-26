import type { AcademyGraduationPilot, AcademyGraduationReviewRequest } from '@dtypes/api.minmatar.org'
import type { ui } from '@i18n/ui'

type UiKey = keyof typeof ui['en']

export type GraduationDecision = AcademyGraduationReviewRequest['decision']

/** Days the timeline spans; older pilots sit on its right edge. */
export const TIMELINE_DAYS = 750
const TIMELINE_BIN_DAYS = 15
/** Cards a board column shows before "See all". */
export const COLUMN_PREVIEW = 3
export const TIMEZONE_FILTERS = ['US', 'EU', 'AP'] as const

const REASON_LABELS: Record<string, UiKey> = {
    eu_skirmish: 'corporations.graduation.reason.eu_skirmish',
    killboard: 'corporations.graduation.reason.killboard',
    large_gang: 'corporations.graduation.reason.large_gang',
    fleet_regular: 'corporations.graduation.reason.fleet_regular',
    building: 'corporations.graduation.reason.building',
    all_timezones: 'corporations.graduation.reason.all_timezones',
}

export function reason_label(reason: string): UiKey {
    return REASON_LABELS[reason] ?? 'corporations.graduation.reason.all_timezones'
}

export interface GraduationBoard {
    due:        AcademyGraduationPilot[];
    training:   AcademyGraduationPilot[];
    kept:       AcademyGraduationPilot[];
    graduating: AcademyGraduationPilot[];
}

/** Pilots by board column. The API sends the review queue first, so `due`
 *  keeps its order; training is sorted by who reaches the review next. */
export function group_pilots(pilots: AcademyGraduationPilot[]): GraduationBoard {
    const board: GraduationBoard = { due: [], training: [], kept: [], graduating: [] }
    for (const pilot of pilots) {
        if (pilot.stage === 'released') continue
        board[pilot.stage].push(pilot)
    }
    board.training.sort((a, b) => b.days_in_academy - a.days_in_academy)
    return board
}

/** The filter tokens a prime time matches: `EU_US` matches EU and US. */
export function timezone_tokens(prime_time: string | null): string[] {
    return (prime_time ?? '').split('_').filter((token) => token.length > 0)
}

/** "EU/US", or the fallback for a pilot with no prime time set. */
export function timezone_label(prime_time: string | null, fallback: string): string {
    const tokens = timezone_tokens(prime_time)
    return tokens.length > 0 ? tokens.join('/') : fallback
}

export type DotTone = 'ready' | 'active' | 'inactive'

export interface TimelineDot {
    character_id:   number;
    character_name: string;
    days:           number;
    left:           number;
    stack:          number;
    tone:           DotTone;
}

/** One dot per pilot along the time-in-Academy axis, stacked in 15-day bins.
 *  `left` is a percentage of the axis; `stack` counts up from the baseline. */
export function timeline_dots(pilots: AcademyGraduationPilot[]): TimelineDot[] {
    const bins = new Map<number, number>()
    // Ready pilots last, so they sit on top of their stack.
    const ordered = [...pilots].sort((a, b) => Number(a.ready) - Number(b.ready))
    return ordered.map((pilot) => {
        const days = Math.min(pilot.days_in_academy, TIMELINE_DAYS - 5)
        const bin = Math.floor(days / TIMELINE_BIN_DAYS)
        const stack = bins.get(bin) ?? 0
        bins.set(bin, stack + 1)
        return {
            character_id: pilot.character_id,
            character_name: pilot.character_name,
            days: pilot.days_in_academy,
            left: Math.round(days / TIMELINE_DAYS * 10000) / 100,
            stack,
            tone: pilot.ready ? 'ready' : pilot.inactive ? 'inactive' : 'active',
        }
    })
}

export function timeline_percent(days: number): number {
    return Math.round(days / TIMELINE_DAYS * 10000) / 100
}

/** The pilot to review: the one asked for, else the head of the queue. */
export function review_target(pilots: AcademyGraduationPilot[], character_id?: number | null) {
    const due = pilots.filter((pilot) => pilot.stage === 'due')
    const asked = character_id ? pilots.find((pilot) => pilot.character_id === character_id) : undefined
    const pilot = asked ?? due[0] ?? null
    const position = pilot ? due.findIndex((item) => item.character_id === pilot.character_id) : -1
    const next = position >= 0 ? due[position + 1] ?? null : due[0] ?? null
    return {
        pilot,
        position: position >= 0 ? position + 1 : null,
        total: due.length,
        next: next && next.character_id !== pilot?.character_id ? next : null,
    }
}

const DECISIONS: GraduationDecision[] = ['graduate', 'keep', 'release']

/** The review form's fields as an API request, or null when malformed. */
export function parse_review_form(form: FormData): AcademyGraduationReviewRequest | null {
    const character_id = parseInt(String(form.get('character_id') ?? ''))
    const decision = String(form.get('decision') ?? '') as GraduationDecision
    if (!character_id || !DECISIONS.includes(decision)) return null
    const corporation_id = parseInt(String(form.get('corporation_id') ?? ''))
    if (decision === 'graduate' && !corporation_id) return null
    return {
        character_id,
        decision,
        corporation_ids: decision === 'graduate' ? [corporation_id] : [],
        note: String(form.get('note') ?? '').slice(0, 1000),
    }
}

/** Fills `{name}` placeholders in a translated string. */
export function fill(template: string, values: Record<string, string | number>): string {
    return template.replace(/\{(\w+)\}/g, (match, key: string) => key in values ? String(values[key]) : match)
}

const TSV_HEADER = ['Pilot', 'TZ', 'Days in Academy', 'SP (M)', 'Fleets 90d', 'Kills 90d', 'Kills 30d', 'Voice h 90d', 'Ready', 'Suggested', 'Stage']

/** The pipeline as tab-separated values for a spreadsheet. */
export function pipeline_tsv(pilots: AcademyGraduationPilot[]): string {
    const clean = (value: string) => value.replace(/[\t\r\n]+/g, ' ')
    const rows = pilots.map((pilot) => [
        clean(pilot.character_name),
        timezone_label(pilot.prime_time, ''),
        String(pilot.days_in_academy),
        pilot.skill_points == null ? '' : String(Math.round(pilot.skill_points / 1_000_000)),
        String(pilot.fleets_90d),
        String(pilot.kills_90d),
        String(pilot.kills_30d),
        String(pilot.voice_hours_90d),
        pilot.ready ? 'yes' : 'no',
        pilot.suggestions.map((suggestion) => suggestion.ticker).join(' / '),
        pilot.stage,
    ].join('\t'))
    return [TSV_HEADER.join('\t'), ...rows].join('\n')
}
