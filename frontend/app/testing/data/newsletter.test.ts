import { existsSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { get_issue, get_latest_issue, ISSUES } from '@/data/newsletter'
import type { NewsletterIssue } from '@/data/newsletter/types'

const PUBLIC_DIR = join(__dirname, '..', '..', 'public')

function local_images(issue: NewsletterIssue): string[] {
    const paths: string[] = []
    if (issue.lead_video) paths.push(issue.lead_video.thumbnail)
    for (const section of issue.sections) {
        if (section.kind === 'feature') paths.push(...(section.figures ?? []).map((figure) => figure.src))
        if (section.kind === 'hits') {
            paths.push(...(section.figures ?? []).map((figure) => figure.src))
            paths.push(...(section.figures_after_orders ?? []).map((figure) => figure.src))
        }
        if (section.kind === 'video') paths.push(section.video.thumbnail)
    }
    return paths
}

describe('newsletter issue registry', () => {
    it('lists yc128-10 as the latest issue', () => {
        expect(get_latest_issue().slug).toBe('yc128-10')
        expect(get_issue('yc128-10')?.permalink_path).toBe('/newsletter/yc128-10/')
        expect(ISSUES).toHaveLength(1)
    })

    it('returns undefined for an unknown slug', () => {
        expect(get_issue('yc128-99')).toBeUndefined()
    })
})

describe('newsletter issue content', () => {
    it.each(ISSUES.map((issue) => [issue.slug, issue] as const))('%s has unique section anchors', (_slug, issue) => {
        const ids = issue.sections.map((section) => section.id)
        expect(new Set(ids).size).toBe(ids.length)
    })

    it.each(ISSUES.map((issue) => [issue.slug, issue] as const))('%s ships every local image it references', (_slug, issue) => {
        for (const src of local_images(issue)) {
            expect(existsSync(join(PUBLIC_DIR, src)), src).toBe(true)
        }
    })

    it.each(ISSUES.map((issue) => [issue.slug, issue] as const))('%s keeps two-column brief lists even', (_slug, issue) => {
        for (const section of issue.sections) {
            if (section.kind === 'hits') expect(section.items.length % 2, section.id).toBe(0)
        }
    })
})
