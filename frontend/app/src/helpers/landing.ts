import type { LandingEvent } from '@dtypes/api.minmatar.org'

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
        case 'type': return `https://images.evetech.net/types/${id}/icon?size=${size}`
        case 'alliance': return `https://images.evetech.net/alliances/${id}/logo?size=${size}`
        case 'corporation': return `https://images.evetech.net/corporations/${id}/logo?size=${size}`
        case 'faction': return MILITIA_CORPORATIONS[id] ? `https://images.evetech.net/corporations/${MILITIA_CORPORATIONS[id]}/logo?size=${size}` : null
        default: return null
    }
}

export function character_portrait(character_id: number, size = 64): string {
    return `https://images.evetech.net/characters/${character_id}/portrait?size=${size}`
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

/** "A Week Of Minmatar Fleet": the last column. Fleet activity shows what
 * each fight destroyed, Warzone the LP each site paid; the other tabs show
 * where it happened. */
export function week_last_column(tab: string): 'isk' | 'lp' | 'region' {
    if (tab === 'fights') return 'isk'
    if (tab === 'warzone') return 'lp'
    return 'region'
}

/** Thresholds for the last column's colour grade: below the first is grade
 * 0 (muted), past each next one a grade brighter, up to 3. */
const AMOUNT_GRADES = {
    isk: [100_000_000, 1_000_000_000, 5_000_000_000],
    lp: [10_000, 25_000, 50_000],
} as const

/** 0 (small, muted) to 3 (biggest), so big fights and fat payouts stand out. */
export function amount_grade(column: 'isk' | 'lp', value: number): 0 | 1 | 2 | 3 {
    return AMOUNT_GRADES[column].filter((step) => value >= step).length as 0 | 1 | 2 | 3
}

export const WEEK_LAST_LABELS = {
    isk: 'landing_new.week_isk',
    lp: 'landing_new.week_lp',
    region: 'landing_new.week_region',
} as const

/** "A Week Of Minmatar Fleet": the grid the partial and its skeleton share. */
export const WEEK_GRID = {
    template: '9rem minmax(0, 1fr) 8rem',
    rows: 12,
} as const

/** The two premium video series found by title: the yearly review and The Cope. */
export const PREMIUM_POST_TITLES = {
    review: /\bin review\b/i,
    cope: /\bthe cope\b/i,
} as const

export type PremiumPostKind = keyof typeof PREMIUM_POST_TITLES

/** The newest post of each premium series, from posts in any order. */
export function pick_premium_posts<T extends { title: string; date_posted: string }>(
    posts: T[],
): Partial<Record<PremiumPostKind, T>> {
    const newest_first = [...posts].sort((a, b) => new Date(b.date_posted).getTime() - new Date(a.date_posted).getTime())
    const picked: Partial<Record<PremiumPostKind, T>> = {}
    for (const kind of Object.keys(PREMIUM_POST_TITLES) as PremiumPostKind[]) {
        const post = newest_first.find((candidate) => PREMIUM_POST_TITLES[kind].test(candidate.title))
        if (post) picked[kind] = post
    }
    return picked
}
