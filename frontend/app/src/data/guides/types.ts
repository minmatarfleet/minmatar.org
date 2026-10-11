export type Author = {
    name: string
    id: number
    entity: 'character' | 'corporation' | 'alliance'
}

export type GuideMeta = {
    slug: string
    title: string
    excerpt: string
    category: string
    /** Optional index subsection within a category. */
    section?: string
    author: string
    authors: Author[]
    path?: string
    hiddenFromIndex?: boolean
    /** Shown on the guides index with a disabled Coming soon state (no page yet). */
    comingSoon?: boolean
    /**
     * Map of section id → Contents group label (cruiser-guide style).
     * Adjacent sections with the same group share one nav subheader.
     */
    contents_groups?: Record<string, string>
    /** Stable TribeGroup.code values this guide belongs to (e.g. capitals.dreads). */
    tribe_group_codes?: string[]
}
