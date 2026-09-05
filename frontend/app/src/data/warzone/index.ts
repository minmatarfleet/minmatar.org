import type { WarzoneIssue } from './types'
import { YC128_07 } from './yc128-07'
import { YC128_08 } from './yc128-08'

export type { WarzoneIssue } from './types'

export const ISSUES: readonly WarzoneIssue[] = [YC128_08, YC128_07]

export function get_latest_issue(): WarzoneIssue {
    const [latest] = [...ISSUES].sort(
        (a, b) => b.published_at.getTime() - a.published_at.getTime(),
    )
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
    const sorted = get_issues_sorted()
    const index = sorted.findIndex((issue) => issue.slug === slug)
    if (index === -1) return {}
    return { newer: sorted[index - 1], older: sorted[index + 1] }
}
