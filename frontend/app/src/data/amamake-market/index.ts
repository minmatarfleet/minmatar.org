import type { AmamakeMarketIssue } from './types'
import { YC128_08 } from './yc128-08'

export type { AmamakeMarketIssue } from './types'

export const LATEST_PATH = '/amamake-market/' as const
export const ALL_REPORTS_PATH = '/alliance/content#AmamakeMarketReports' as const

export const ISSUES: readonly AmamakeMarketIssue[] = [YC128_08]

export function get_latest_issue(): AmamakeMarketIssue {
    const [latest] = get_issues_sorted()
    if (!latest) {
        throw new Error('No Amamake market issues registered')
    }
    return latest
}

export function get_issue(slug: string): AmamakeMarketIssue | undefined {
    return ISSUES.find((issue) => issue.slug === slug)
}

export function get_issue_slugs(): string[] {
    return ISSUES.map((issue) => issue.slug)
}

/** Issues newest-first. */
export function get_issues_sorted(): AmamakeMarketIssue[] {
    return [...ISSUES].sort((a, b) => b.published_at.getTime() - a.published_at.getTime())
}

/**
 * Neighbouring issues for on-report navigation. `newer` is the issue published
 * after this one (toward the latest), `older` the one before it.
 */
export function get_adjacent_issues(slug: string): {
    newer?: AmamakeMarketIssue
    older?: AmamakeMarketIssue
} {
    const sorted = get_issues_sorted()
    const index = sorted.findIndex((issue) => issue.slug === slug)
    if (index === -1) return {}
    return { newer: sorted[index - 1], older: sorted[index + 1] }
}

/** Short series label, e.g. "August YC128", from the issue's publish date. */
export function issue_label(issue: AmamakeMarketIssue): string {
    const month = issue.published_at.toLocaleString('en-US', { month: 'long', timeZone: 'UTC' })
    return `${month} YC${issue.published_at.getUTCFullYear() - 1898}`
}
