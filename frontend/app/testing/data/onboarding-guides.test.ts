import { describe, expect, it } from 'vitest'

import {
    getGuideBySlug,
    getGuidesByCategory,
    guideSectionsByCategory,
    guides,
} from '@/data/guides'

const ONBOARDING_ORDER = [
    'onboarding-home-base',
    'onboarding-first-fleet',
    'onboarding-fleet-types-and-hangar',
    'onboarding-faction-warfare-essentials',
    'onboarding-first-billion',
    'onboarding-make-content',
    'onboarding-trial-srp-help',
    'onboarding-culture-map',
]

const MARKDOWN_LINK = /\]\((\/[^)\s#]*)/g

describe('onboarding guides', () => {
    it('lists the series in day one → trial order', () => {
        const slugs = getGuidesByCategory()['Onboarding'].map((guide) => guide.slug)
        expect(slugs).toEqual(ONBOARDING_ORDER)
    })

    it('puts every guide in a configured stage, in stage order', () => {
        const stages = guideSectionsByCategory['Onboarding'] ?? []
        expect(stages).toEqual(['Day One', 'Week One', 'Month One', 'Trial'])

        const stage_indexes = ONBOARDING_ORDER.map((slug) =>
            stages.indexOf(getGuideBySlug(slug)?.section ?? ''),
        )
        expect(stage_indexes).not.toContain(-1)
        expect([...stage_indexes].sort()).toEqual(stage_indexes)
    })

    it('has markdown whose frontmatter matches the registry', () => {
        for (const slug of ONBOARDING_ORDER) {
            const guide = getGuideBySlug(slug)
            expect(guide, slug).toBeDefined()
            expect(guide!.module.frontmatter.title).toBe(guide!.title)
            expect(guide!.module.frontmatter.category).toBe('Onboarding')
            expect(guide!.module.rawContent()).toContain('## ')
        }
    })

    it('links only to guides that exist', () => {
        const known = new Set(guides.filter((guide) => !guide.comingSoon).map((guide) => guide.slug))
        for (const slug of ONBOARDING_ORDER) {
            const markdown = getGuideBySlug(slug)!.module.rawContent()
            for (const [, path] of markdown.matchAll(MARKDOWN_LINK)) {
                const linked = path.match(/^\/learning\/guides\/([^/]+)\/$/)
                if (linked) expect(known.has(linked[1]), `${slug} → ${path}`).toBe(true)
            }
        }
    })
})
