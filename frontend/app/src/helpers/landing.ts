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

/** "BearThatCares and 8 others" from an event and the translated suffix. */
export function event_who(event: LandingEvent, others_template: string): string {
    if (!event.others) return event.character_name
    return `${event.character_name} ${others_template.replace('{count}', String(event.others))}`
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
