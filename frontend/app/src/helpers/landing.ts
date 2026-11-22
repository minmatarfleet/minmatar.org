import type { LandingEvent } from '@dtypes/api.minmatar.org'
import { get_alliance_logo, get_corporation_logo, get_player_icon, get_type_icon } from '@helpers/eve_image'

/** HH:MM in EVE time (UTC). */
export function eve_clock(iso: string): string {
    return new Date(iso).toISOString().slice(11, 16)
}

/** "Tue 17 Nov" in EVE time. */
export function eve_day(iso: string): string {
    return new Date(iso).toLocaleDateString('en-GB', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        timeZone: 'UTC',
    })
}

export function format_number(value: number): string {
    return Math.round(value).toLocaleString('en-US')
}

/** "BearThatCares and 8 others" (or "and 1 other") from an event and the translated suffixes. */
export function event_who(event: LandingEvent, others_template: string, other_template: string = others_template): string {
    if (!event.others) return event.character_name
    const template = event.others === 1 ? other_template : others_template
    return `${event.character_name} ${template.replace('{count}', String(event.others))}`
}

/** A militia's logo is its militia corporation's. */
const MILITIA_CORPORATIONS: Record<number, number> = {
    500001: 1000180,
    500002: 1000182,
    500003: 1000179,
    500004: 1000181,
    500010: 1000127,
    500011: 1000124,
}

/** The image-server icon for a line's subject: a ship or ore, or the side we fought. */
export function subject_icon(event: Pick<LandingEvent, 'subject_type' | 'subject_id'>, size = 32): string | null {
    const id = event.subject_id
    if (!id) return null
    switch (event.subject_type) {
        case 'type': return get_type_icon(id, size)
        case 'alliance': return get_alliance_logo(id, size)
        case 'corporation': return get_corporation_logo(id, size)
        case 'faction': return MILITIA_CORPORATIONS[id] ? get_corporation_logo(MILITIA_CORPORATIONS[id], size) : null
        default: return null
    }
}

export interface LandingDayStats {
    ships_destroyed: number;
    warzone_sites: number;
    complexes: number;
    mined_volume: number;
}

/** What one Live line adds to the 24-hour numbers. */
export function stat_adds(event: LandingEvent): Partial<LandingDayStats> {
    if (event.kind === 'kill') return { ships_destroyed: 1 }
    if (event.kind === 'site') return event.verb === 'captured a complex' ? { warzone_sites: 1, complexes: 1 } : { warzone_sites: 1 }
    if (event.kind === 'mining') return { mined_volume: event.amount ?? 0 }
    return {}
}

/**
 * The 24-hour numbers after each step of the Live band's playback. `played`
 * is oldest first; `totals` already include every line, so step 0 is the
 * totals minus whatever is still to play, and the last step is the totals.
 */
export function stat_steps(totals: LandingDayStats, played: LandingEvent[], start: number): LandingDayStats[] {
    const keys = Object.keys(totals) as (keyof LandingDayStats)[]
    const current = { ...totals }
    for (const event of played.slice(start + 1)) {
        const adds = stat_adds(event)
        for (const key of keys) current[key] -= adds[key] ?? 0
    }
    const steps = [{ ...current }]
    for (const event of played.slice(start + 1)) {
        const adds = stat_adds(event)
        for (const key of keys) current[key] += adds[key] ?? 0
        steps.push({ ...current })
    }
    return steps
}

/** 17.7M / 368K / 950 */
export function short_number(value: number): string {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
    if (value >= 10_000) return `${Math.round(value / 1000)}K`
    return format_number(value)
}

export function character_portrait(character_id: number, size = 64): string {
    return get_player_icon(character_id, size)
}

/** Bar heights as percentages of the tallest bar; never below a stub. */
export function bar_heights(values: number[], min_percent = 4): number[] {
    const max = Math.max(1, ...values)
    return values.map((value) => Math.max(min_percent, Math.round((value / max) * 100)))
}

/** Title without a trailing "(Reddit)"-style copy marker, for matching. */
function post_key(title: string): string {
    return title.replace(/\s*\((reddit|discord|forums?|copy)\)\s*$/i, '').trim().toLowerCase()
}

/**
 * One card per story: cross-posts like "Title (Reddit)" or a second post with
 * the same cover image collapse into the first. When the kept copy is the
 * marked one, the plain title wins. Order is kept.
 */
export function dedupe_posts<T extends { title: string; image?: string }>(posts: T[]): T[] {
    const kept: T[] = []
    const by_title = new Map<string, number>()
    const by_image = new Map<string, number>()
    for (const post of posts) {
        const key = post_key(post.title)
        const index = by_title.get(key) ?? (post.image ? by_image.get(post.image) : undefined)
        if (index === undefined) {
            by_title.set(key, kept.length)
            if (post.image) by_image.set(post.image, kept.length)
            kept.push(post)
            continue
        }
        if (post_key(post.title) === post.title.trim().toLowerCase() && kept[index].title.trim().toLowerCase() !== key)
            kept[index] = post
    }
    return kept
}
