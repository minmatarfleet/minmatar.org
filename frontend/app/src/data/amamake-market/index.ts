import type { AmamakeMarketIssue, MarketTopTypeRow } from './types'
import { YC128_08 } from './yc128-08'

export type { AmamakeMarketIssue } from './types'
export { is_skin_or_blueprint, without_skins_and_blueprints } from './sales_filters'

export const SOLD_CLASS_ALL = 'all' as const

const SOLD_CLASS_SHORT_LABEL: Readonly<Record<string, string>> = {
    Ships: 'Ships',
    Modules: 'Modules',
    Rigs: 'Rigs',
    Charges: 'Charges',
    Drones: 'Drones',
    'PLEX adjacent': 'PLEX adjacent',
    Implants: 'Implants',
    'Materials & commodities': 'Materials',
    Other: 'Other',
}

/** URL slug for a generated class bucket, e.g. "PLEX adjacent" → "plex-adjacent". */
export function sold_class_slug(name: string): string {
    return name
        .toLowerCase()
        .replace(/&/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
}

export function sold_class_label(name: string): string {
    return SOLD_CLASS_SHORT_LABEL[name] ?? name
}

/** Average % over Jita. Em-dash when the type/class has no Forge average — never a fake 0%. */
export function format_markup_pct(pct: number | null): string {
    if (pct === null) return '—'
    return `${pct > 0 ? '+' : ''}${pct}%`
}

/** Class buckets that have at least one inferred-ISK row, in the month's ISK order. */
export function get_sold_class_names(issue: AmamakeMarketIssue): string[] {
    return issue.categories
        .map((row) => row.name)
        .filter((name) => (issue.top_types.by_class[name]?.length ?? 0) > 0)
}

export function resolve_sold_types(
    issue: AmamakeMarketIssue,
    sold_class: string | null | undefined,
): {
    slug: string
    class_name: string | null
    rows: readonly MarketTopTypeRow[]
} {
    const requested = sold_class?.trim() || SOLD_CLASS_ALL
    if (requested === SOLD_CLASS_ALL) {
        return { slug: SOLD_CLASS_ALL, class_name: null, rows: issue.top_types.rows }
    }
    const class_name = get_sold_class_names(issue).find((name) => sold_class_slug(name) === requested)
    if (!class_name) {
        return { slug: SOLD_CLASS_ALL, class_name: null, rows: issue.top_types.rows }
    }
    return {
        slug: requested,
        class_name,
        rows: issue.top_types.by_class[class_name] ?? [],
    }
}

export const LATEST_PATH = '/amamake-market/' as const
export const ALL_REPORTS_PATH = '/alliance/content#WarzoneReports' as const

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
