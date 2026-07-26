import { marked, Renderer } from 'marked'
import { renderer as baseRenderer } from '@helpers/marked'
import { extractMarkdownSections, slugifySectionId } from '@helpers/pageProgress/sections'

/**
 * Parse markdown so each `##` heading gets `id` + `data-section-id`
 * matching {@link extractMarkdownSections}.
 */
export function parseMarkdownWithSections(markdown: string): string {
    const sections = extractMarkdownSections(markdown)
    const idByRawTitle = new Map(sections.map((section) => [section.title, section.id]))
    const usedIds = new Set<string>()

    const progressRenderer = new Renderer()
    progressRenderer.link = baseRenderer.link.bind(baseRenderer)

    progressRenderer.heading = (text: string, level: number, raw: string) => {
        if (level !== 2) {
            return `<h${level}>${text}</h${level}>\n`
        }

        const title = (raw || text).replace(/<[^>]+>/g, '').trim()
        let id = idByRawTitle.get(title)
        if (!id) {
            id = slugifySectionId(title)
            if (usedIds.has(id)) {
                let n = 2
                while (usedIds.has(`${id}-${n}`)) n += 1
                id = `${id}-${n}`
            }
        }
        usedIds.add(id)
        return `<h2 id="${id}" data-section-id="${id}">${text}</h2>\n`
    }

    return marked.parse(markdown, { renderer: progressRenderer }) as string
}
