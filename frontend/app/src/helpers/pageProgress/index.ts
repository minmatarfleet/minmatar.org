/**
 * Page progress — track whether users have read page sections.
 *
 * ## Wiring a page (3 steps)
 *
 * 1. Build a manifest with `pageProgressFromMarkdown` or `pageProgressFromSections`.
 * 2. Put `data-page-progress-root` on a parent that wraps the tracker + sections.
 * 3. Mount `<PageProgress {...progress} />` and mark sections
 *    (`progress.html` for markdown, or `<PageProgressSection id="…" />` / `data-section-id`).
 *
 * Anonymous visitors get localStorage progress; on login it merges to the server.
 * Auth labels are handled by `<PageProgress />`.
 */

export type { PageProgressProps, PageProgressSection } from '@helpers/pageProgress/sections'
export {
    extractMarkdownSections,
    hashPageVersion,
    normalizeSectionIds,
    slugifySectionId,
} from '@helpers/pageProgress/sections'
export { parseMarkdownWithSections } from '@helpers/pageProgress/markdown'
export {
    pageProgressFromMarkdown,
    pageProgressFromSections,
    type MarkdownPageProgress,
} from '@helpers/pageProgress/manifest'
export { DWELL_MS, VISIBLE_RATIO } from '@helpers/pageProgress/dwellObserver'
export {
    LOCAL_STORE_KEY,
    MAX_SECTIONS_PER_PAGE,
    ackPageLocal,
    clearAll,
    clearPage,
    loadPage,
    loadStore,
    markSectionLocal,
    progressPercent,
    takePendingForImport,
    type LocalPageProgress,
    type LocalPageProgressImport,
    type LocalPageProgressStore,
} from '@helpers/pageProgress/localStore'
