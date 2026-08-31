import type { WarzoneIssue } from './types'
import { YC128_07 } from './yc128-07'

export type { WarzoneIssue } from './types'

export const ISSUES: readonly WarzoneIssue[] = [YC128_07]

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
