import { createHash } from 'node:crypto'

export type PageProgressSection = {
    id: string
    title: string
}

/** Props accepted by `<PageProgress />`. */
export type PageProgressProps = {
    page_key: string
    page_title: string
    version: string
    section_ids: string[]
}

const HEADING_RE = /^##\s+(.+?)\s*$/gm

/** Slugify a heading/title into a stable section id. */
export function slugifySectionId(title: string): string {
    return title
        .trim()
        .toLowerCase()
        .replace(/['']/g, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
}

/** Extract top-level (`##`) markdown headings as trackable sections. */
export function extractMarkdownSections(markdown: string): PageProgressSection[] {
    const sections: PageProgressSection[] = []
    const seen = new Set<string>()
    for (const match of markdown.matchAll(HEADING_RE)) {
        const title = (match[1] ?? '').trim()
        if (!title) continue
        let id = slugifySectionId(title)
        if (!id) continue
        if (seen.has(id)) {
            let n = 2
            while (seen.has(`${id}-${n}`)) n += 1
            id = `${id}-${n}`
        }
        seen.add(id)
        sections.push({ id, title })
    }
    return sections
}

/** Short content hash used as the page progress version. */
export function hashPageVersion(content: string): string {
    return createHash('sha256').update(content).digest('hex').slice(0, 16)
}

export function normalizeSectionIds(
    sections: Array<string | { id: string; title?: string }>,
): string[] {
    return sections.map((section) => (typeof section === 'string' ? section : section.id))
}
