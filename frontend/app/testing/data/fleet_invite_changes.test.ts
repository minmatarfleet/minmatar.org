import { describe, expect, it } from 'vitest'

import { bar_percent, bar_tip, fleet_invite_changes, RESPONSES } from '@/data/fleet_invite_changes'
import { getPublicSitemapPagePaths } from '@helpers/sitemap_xml'

describe('fleet invite release notes', () => {
    it('scales bars to the largest row', () => {
        for (const chart of fleet_invite_changes.charts) {
            const widths = chart.rows.map((row) => bar_percent(row.count, chart.rows))
            expect(Math.max(...widths)).toBe(100)
            widths.forEach((width) => expect(width).toBeGreaterThan(0))
        }
    })

    it('keeps every chart row within its question total', () => {
        for (const chart of fleet_invite_changes.charts) {
            expect(chart.total).toBeLessThanOrEqual(RESPONSES)
            const sum = chart.rows.reduce((total, row) => total + row.count, 0)
            expect(sum).toBeLessThanOrEqual(chart.total)
        }
    })

    it('writes the tooltip as "label: n of total (p%)"', () => {
        expect(bar_tip({ label: 'I barely noticed it', count: 10 }, 116)).toBe('I barely noticed it: 10 of 116 (9%)')
        expect(bar_percent(0, [])).toBe(0)
    })

    it('says the changes are live', () => {
        expect(fleet_invite_changes.changing_intro).toBe('These are live now.')
        expect(fleet_invite_changes.changes).toHaveLength(3)
    })

    it('is a public sitemap page', () => {
        expect(getPublicSitemapPagePaths()).toContain('/fleets/invite-feedback/results/')
    })
})
