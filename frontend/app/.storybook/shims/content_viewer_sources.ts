// Browser stand-in for src/helpers/content_viewer_sources.ts in the preview
// bundle. ContentViewer and ContentViewerLink import the registry in their
// frontmatter, and it imports every viewable page's data, including markdown
// the browser build can't parse. Frontmatter only runs on the render server,
// which loads the real module.
import type { ViewerTarget } from '../../src/helpers/content_viewer_sources'

export type { ViewerSource, ViewerTarget, ViewerWidth } from '../../src/helpers/content_viewer_sources'

export const VIEWER_SOURCES = ['post', 'guide', 'warzone', 'market', 'newsletter', 'values', 'story'] as const

export function resolve_viewer_path(): ViewerTarget | null {
    return null
}

export function viewer_client_routes(): { paths: string[], post: string } {
    return { paths: [], post: '$^' }
}

export function viewer_query(target: ViewerTarget): string {
    return `source=${target.source}&id=${encodeURIComponent(target.id)}`
}
