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
    /** Optional index subsection within a category (e.g. Mechanics / Ships). */
    section?: string
    author: string
    authors: Author[]
    path?: string
    hiddenFromIndex?: boolean
    /**
     * Map of section id → Contents group label (cruiser-guide style).
     * Adjacent sections with the same group share one nav subheader.
     */
    contents_groups?: Record<string, string>
}
