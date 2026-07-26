/**
 * Compatibility shims — prefer `@helpers/pageProgress`.
 * @deprecated Use `@helpers/pageProgress` instead.
 */
export type { PageProgressSection as GuideSectionRef } from '@helpers/pageProgress/sections'
export {
    extractMarkdownSections,
    hashPageVersion,
    slugifySectionId,
} from '@helpers/pageProgress/sections'

export function guidePageKey(slug: string): string {
    return `guides/${slug}`
}
