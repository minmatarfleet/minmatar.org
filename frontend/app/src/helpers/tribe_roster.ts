import type { TribeGroupRosterEntry } from '@dtypes/api.minmatar.org'

export type TribeRosterSection = {
    key: string
    /** Section heading; null means render a flat list with no header. */
    heading: string | null
    show_rank_on_cards: boolean
    members: TribeGroupRosterEntry[]
}

export type TribeRosterCorporationFilter = {
    id: string
    corporation_id: number | null
    label: string
    count: number
}

function by_character_name(
    a: TribeGroupRosterEntry,
    b: TribeGroupRosterEntry,
): number {
    return a.primary_character_name.localeCompare(
        b.primary_character_name,
        undefined,
        { sensitivity: 'base' },
    )
}

function by_filter_label(
    a: TribeRosterCorporationFilter,
    b: TribeRosterCorporationFilter,
): number {
    return a.label.localeCompare(b.label, undefined, { sensitivity: 'base' })
}

export function corporation_filter_id(
    corporation_id: number | null | undefined,
): string {
    return corporation_id != null ? String(corporation_id) : 'none'
}

/**
 * Build corporation filter chips for a roster. Returns empty when filtering
 * would be pointless (zero or one distinct corporation).
 */
export function roster_corporation_filters(
    roster: TribeGroupRosterEntry[],
    all_label: string,
    unknown_label: string,
): TribeRosterCorporationFilter[] {
    const counts = new Map<string, TribeRosterCorporationFilter>()

    for (const entry of roster) {
        const id = corporation_filter_id(entry.corporation_id)
        const existing = counts.get(id)
        if (existing) {
            existing.count += 1
            continue
        }
        counts.set(id, {
            id,
            corporation_id: entry.corporation_id,
            label: entry.corporation_name?.trim()
                ? entry.corporation_name
                : unknown_label,
            count: 1,
        })
    }

    if (counts.size <= 1) return []

    const corp_filters = [...counts.values()].sort(by_filter_label)

    return [
        {
            id: 'all',
            corporation_id: null,
            label: all_label,
            count: roster.length,
        },
        ...corp_filters,
    ]
}

/**
 * Group a tribe-group roster by rank when multiple ranks are in use.
 * Flat list when nobody has a rank, or everyone shares the same rank.
 */
export function group_roster_by_rank(
    roster: TribeGroupRosterEntry[],
    unranked_heading: string,
): TribeRosterSection[] {
    const ranked = roster.filter((entry) => entry.rank_id != null)
    const unranked = roster.filter((entry) => entry.rank_id == null)
    const distinct_rank_ids = new Set(ranked.map((entry) => entry.rank_id))

    if (distinct_rank_ids.size === 0) {
        return [{
            key: 'all',
            heading: null,
            show_rank_on_cards: false,
            members: [...roster].sort(by_character_name),
        }]
    }

    if (distinct_rank_ids.size === 1 && unranked.length === 0) {
        return [{
            key: 'all',
            heading: null,
            show_rank_on_cards: false,
            members: [...roster].sort(by_character_name),
        }]
    }

    const sections_by_rank = new Map<number, TribeRosterSection>()

    for (const entry of ranked) {
        const rank_id = entry.rank_id as number
        let section = sections_by_rank.get(rank_id)
        if (!section) {
            section = {
                key: `rank-${rank_id}`,
                heading: entry.rank_name || unranked_heading,
                show_rank_on_cards: false,
                members: [],
            }
            sections_by_rank.set(rank_id, section)
        }
        section.members.push(entry)
    }

    const ranked_sections = [...sections_by_rank.values()].sort((a, b) => {
        const a_order = a.members[0]?.rank_sort_order ?? Number.MAX_SAFE_INTEGER
        const b_order = b.members[0]?.rank_sort_order ?? Number.MAX_SAFE_INTEGER
        if (a_order !== b_order) return a_order - b_order
        return (a.heading ?? '').localeCompare(b.heading ?? '', undefined, {
            sensitivity: 'base',
        })
    })

    for (const section of ranked_sections) {
        section.members.sort(by_character_name)
    }

    if (unranked.length > 0) {
        ranked_sections.push({
            key: 'unranked',
            heading: unranked_heading,
            show_rank_on_cards: false,
            members: [...unranked].sort(by_character_name),
        })
    }

    return ranked_sections
}
