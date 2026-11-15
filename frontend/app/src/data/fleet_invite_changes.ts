/**
 * Release notes for the November 2026 fleet invite survey: what pilots told
 * us and what changed. Copy lives here (English only, like the newsletter);
 * the page and meta titles live in i18n.
 */

export interface InviteChangesStat {
    value: string
    /** Smaller trailing part of the value, e.g. " of 116". */
    suffix?: string
    label: string
}

export interface InviteChangesBarRow {
    label: string
    count: number
}

export interface InviteChangesChart {
    title: string
    /** Pilots who answered this question: the base of each row's percentage. */
    total: number
    rows: InviteChangesBarRow[]
}

export interface InviteChangesItem {
    title: string
    text: string
}

export interface InviteChanges {
    kicker: string
    intro: string
    stats: InviteChangesStat[]
    told_title: string
    charts: InviteChangesChart[]
    quotes: string[]
    quote_by: string
    changing_title: string
    changing_intro: string
    changes: InviteChangesItem[]
    later_title: string
    later: InviteChangesItem[]
}

export const RESPONSES = 116

export const fleet_invite_changes: InviteChanges = {
    kicker: 'Fleet invites · Release notes · 14 Nov 2026',
    intro: 'We sent a short Discord survey out on how fleet invitations were performing, and received some valuable feedback.',
    stats: [
        { value: '100%', label: 'were glad or fine to receive an invitation' },
        { value: '114', suffix: ` of ${RESPONSES}`, label: 'want direct invites to keep coming' },
        { value: '43', suffix: ` of ${RESPONSES}`, label: "weren't sure Sitting out was harmless" },
    ],
    told_title: 'What you told us',
    charts: [
        {
            title: 'What pressing Sitting out felt like',
            total: RESPONSES,
            rows: [
                { label: 'A normal "not this time"', count: 73 },
                { label: 'Like it might turn invites off', count: 16 },
                { label: "Like I'd be letting the FC down", count: 11 },
                { label: 'I barely noticed it', count: 10 },
                { label: "I wasn't sure what it did", count: 6 },
            ],
        },
        {
            title: 'Why invites went unanswered',
            total: 71,
            rows: [
                { label: "Other, mostly didn't see it in time", count: 32 },
                { label: 'Meant to decide later, then forgot', count: 19 },
                { label: 'Saying nothing felt like no', count: 12 },
                { label: 'It was awkward on my phone', count: 4 },
                { label: "Didn't want a no written down", count: 2 },
            ],
        },
    ],
    quotes: [
        "I didn't realize they required a response until the 3rd. I just assumed they were pings.",
        "Just don't be offended or stop inviting me if I happen to miss a few.",
        'A maybe option. Kids are unpredictable.',
    ],
    quote_by: 'A pilot',
    changing_title: "What we're changing",
    changing_intro: 'These are live now.',
    changes: [
        {
            title: 'Answer from your phone without signing in',
            text: 'Press “I\'m available” in Discord and you get a temporary signup form for your phone that requires no login and can be submitted in under a minute.',
        },
        {
            title: 'Buttons clarify what they mean a bit better',
            text: 'We\'ve changed them to “I\'m available” and “I\'m not available” to help folks understand what they\'re clicking.',
        },
        {
            title: 'Room for real life',
            text: 'Mark your confidence of showing up so that the FC understands a portion of their fleet might not be 100%.',
        },
    ],
    later_title: 'Not yet, but we heard you',
    later: [
        {
            title: 'Invites at the wrong time of day',
            text: 'The most-asked request: 9 of you want invites that fit your timezone or the hours you play. Invites already follow the fleet\'s start time, so some are still slipping through. We\'re counting how many before deciding between a fix and a "when I can fly" setting.',
        },
        {
            title: 'Ship picker bugs',
            text: 'Two of you hit problems picking ships: a ship named in a fleet\'s description that wasn\'t in the list, and picks that didn\'t seem to save. We\'re tracking both down before the new picker ships.',
        },
    ],
}

/** Bar width as a share of the largest row, so the top row fills the track. */
export function bar_percent(count: number, rows: InviteChangesBarRow[]): number {
    const max = rows.reduce((top, row) => Math.max(top, row.count), 0)
    return max ? Math.round((100 * count) / max) : 0
}

/** Native tooltip and screen-reader text: "label: n of total (p%)". */
export function bar_tip(row: InviteChangesBarRow, total: number): string {
    const share = total ? Math.round((100 * row.count) / total) : 0
    return `${row.label}: ${row.count} of ${total} (${share}%)`
}
