import { parseMarkdownWithSections } from '@helpers/pageProgress/markdown'
import {
    extractMarkdownSections,
    hashPageVersion,
    normalizeSectionIds,
    type PageProgressProps,
    type PageProgressSection,
} from '@helpers/pageProgress/sections'

export type MarkdownPageProgress = PageProgressProps & {
    /** HTML with `##` headings tagged for tracking — render with set:html. */
    html: string
    /** Top-level `##` sections (ids match heading anchors in `html`). */
    sections: PageProgressSection[]
}

/**
 * Build progress props + tagged HTML from markdown that uses `##` sections.
 *
 * @example
 * const { html, sections, ...progress } = pageProgressFromMarkdown({
 *   page_key: 'alliance/values',
 *   page_title: 'Alliance Values',
 *   markdown: raw,
 * })
 * // <PageProgress {...progress} />
 * // <div set:html={html} />
 */
export function pageProgressFromMarkdown(options: {
    page_key: string
    page_title: string
    markdown: string
}): MarkdownPageProgress {
    const sections = extractMarkdownSections(options.markdown)
    return {
        page_key: options.page_key,
        page_title: options.page_title,
        version: hashPageVersion(options.markdown),
        section_ids: sections.map((section) => section.id),
        sections,
        html: parseMarkdownWithSections(options.markdown),
    }
}

/**
 * Build progress props from an explicit section list (custom Astro pages).
 *
 * @example
 * const progress = pageProgressFromSections({
 *   page_key: 'guides/navy-destroyer-metagame',
 *   page_title: 'Navy Destroyer Guide',
 *   sections: ['credits', 'history', 'introduction'],
 * })
 * // Mark DOM: <PageProgressSection id="credits">...</PageProgressSection>
 */
export function pageProgressFromSections(options: {
    page_key: string
    page_title: string
    sections: Array<string | { id: string; title?: string }>
    /** Bump when content changes; defaults to JSON of section ids. */
    version_source?: string
}): PageProgressProps {
    const section_ids = normalizeSectionIds(options.sections)
    return {
        page_key: options.page_key,
        page_title: options.page_title,
        version: hashPageVersion(options.version_source ?? JSON.stringify(section_ids)),
        section_ids,
    }
}
