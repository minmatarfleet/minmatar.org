import type { NewsletterIssue } from './types'
import { YC128_10 } from './yc128-10'

export type { NewsletterIssue } from './types'

export const ISSUES: readonly NewsletterIssue[] = [YC128_10]

/** Issues newest-first. */
export function get_issues_sorted(): NewsletterIssue[] {
    return [...ISSUES].sort((a, b) => b.published_at.getTime() - a.published_at.getTime())
}

export function get_latest_issue(): NewsletterIssue {
    const [latest] = get_issues_sorted()
    if (!latest) {
        throw new Error('No newsletter issues registered')
    }
    return latest
}

export function get_issue(slug: string): NewsletterIssue | undefined {
    return ISSUES.find((issue) => issue.slug === slug)
}
