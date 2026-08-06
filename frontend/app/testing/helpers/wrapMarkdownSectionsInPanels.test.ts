import { describe, expect, it } from 'vitest'

import {
    parseMarkdownWithSections,
    wrapMarkdownSectionsInPanels,
} from '@helpers/pageProgress/markdown'

describe('wrapMarkdownSectionsInPanels', () => {
    it('wraps tagged h2 sections into guide-md panels', () => {
        const html = parseMarkdownWithSections(`## Overview

Hello.

## Systems

World.
`)
        const wrapped = wrapMarkdownSectionsInPanels(html)

        expect(wrapped).toContain('class="guide-md-section guide-md-panel"')
        expect(wrapped).toContain('id="overview" data-section-id="overview"')
        expect(wrapped).toContain('id="systems" data-section-id="systems"')
        expect(wrapped).toContain('class="guide-md-section__title">Overview</h2>')
        expect(wrapped).not.toMatch(/<h2[^>]*data-section-id=/)
    })

    it('preserves preamble before the first section', () => {
        const html = '<p>Lead-in</p>\n<h2 id="overview" data-section-id="overview">Overview</h2>\n<p>Body</p>\n'
        const wrapped = wrapMarkdownSectionsInPanels(html)

        expect(wrapped).toContain('class="guide-md-preamble"')
        expect(wrapped).toContain('Lead-in')
        expect(wrapped).toContain('data-section-id="overview"')
    })
})
