import type { WarzoneIssue, WarzoneMilitiaId, WarzoneZoneId } from './types'
import { YC128_07 } from './yc128-07'
import { YC128_08 } from './yc128-08'
import { YC128_09 } from './yc128-09'
import { YC128_10 } from './yc128-10'
import { GALLENTE_CALDARI_YC128_10 } from './gallente-caldari-yc128-10'

export type { WarzoneIssue, WarzoneZoneId } from './types'

export const ZONE_SIDES: Record<WarzoneZoneId, readonly [WarzoneMilitiaId, WarzoneMilitiaId]> = { // pragma: allowlist secret
    'amarr-minmatar': ['minmatar', 'amarr'], // pragma: allowlist secret
    'gallente-caldari': ['gallente', 'caldari'],
}

export const ISSUES: readonly WarzoneIssue[] = [YC128_10, GALLENTE_CALDARI_YC128_10, YC128_09, YC128_08, YC128_07] // pragma: allowlist secret

export function issue_zone(issue: WarzoneIssue): WarzoneZoneId {
    return issue.zone ?? 'amarr-minmatar' // pragma: allowlist secret
}

export function get_issues_in_zone(zone: WarzoneZoneId): WarzoneIssue[] {
    return get_issues_sorted().filter((issue) => issue_zone(issue) === zone)
}

export function get_latest_issue_in_zone(zone: WarzoneZoneId): WarzoneIssue | undefined {
    return get_issues_in_zone(zone)[0]
}

/** Latest Amarr–Minmatar issue. `/warzone/` stays that series. */ // pragma: allowlist secret
export function get_latest_issue(): WarzoneIssue {
    const latest = get_latest_issue_in_zone('amarr-minmatar') // pragma: allowlist secret
    if (!latest) {
        throw new Error('No warzone issues registered')
    }
    return latest
}

export function get_issue(slug: string): WarzoneIssue | undefined {
    return ISSUES.find((issue) => issue.slug === slug)
}

export function get_issue_slugs(): string[] {
    return ISSUES.map((issue) => issue.slug)
}

/** Issues newest-first. */
export function get_issues_sorted(): WarzoneIssue[] {
    return [...ISSUES].sort((a, b) => b.published_at.getTime() - a.published_at.getTime())
}

/**
 * Neighbouring issues for on-report navigation. `newer` is the issue published
 * after this one (toward the latest), `older` the one before it.
 */
export function get_adjacent_issues(slug: string): {
    newer?: WarzoneIssue
    older?: WarzoneIssue
} {
    const issue = get_issue(slug)
    if (!issue) return {}
    const sorted = get_issues_in_zone(issue_zone(issue))
    const index = sorted.findIndex((candidate) => candidate.slug === slug)
    if (index === -1) return {}
    return { newer: sorted[index - 1], older: sorted[index + 1] }
}
