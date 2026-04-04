export function fitting_tag_label(slug: string, t: (key: string) => string): string {
    const key = `fitting.tag.${slug}`
    const label = t(key as any)
    return !label || label === key ? slug.replace(/_/g, ' ') : label
}

/**
 * Human-readable fitting tag line for UI (matches backend FittingTag labels via i18n).
 */
export function format_fitting_tags_line(
    tags: string[] | undefined,
    t: (key: string) => string,
): string {
    if (!tags?.length) return ''
    return [...tags].sort().map((slug) => fitting_tag_label(slug, t)).join(', ')
}
