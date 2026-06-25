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
    author: string
    authors: Author[]
    path?: string
    hiddenFromIndex?: boolean
}
