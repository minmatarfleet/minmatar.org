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

/**
 * Wrap each tagged `##` block in a cruiser-guide-style panel section.
 * Moves `id` / `data-section-id` onto the `<section>` (matches ship guides).
 */
export function wrapMarkdownSectionsInPanels(html: string): string {
    const chunks = html.split(/(?=<h2\b[^>]*\bdata-section-id=)/i)
    const out: string[] = []

    for (const chunk of chunks) {
        const match = chunk.match(/^<h2\b([^>]*)>([\s\S]*?)<\/h2>([\s\S]*)$/i)
        if (!match) {
            if (chunk.trim()) {
                out.push(`<div class="guide-md-preamble">${chunk}</div>`)
            }
            continue
        }

        const attrs = match[1] ?? ''
        const title_html = match[2] ?? ''
        const body_html = match[3] ?? ''
        const id_match = attrs.match(/\bdata-section-id="([^"]+)"/i)
        const id = id_match?.[1] ?? ''
        if (!id) {
            out.push(chunk)
            continue
        }

        out.push(
            `<section id="${id}" data-section-id="${id}" class="guide-md-section guide-md-panel">` +
                `<h2 class="guide-md-section__title">${title_html}</h2>` +
                body_html +
            `</section>`,
        )
    }

    return out.join('\n')
}
