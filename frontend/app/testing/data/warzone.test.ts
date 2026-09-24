import { describe, expect, it } from 'vitest'

import { get_issue, get_issue_slugs, get_latest_issue, ISSUES } from '@/data/warzone'
import { getWarzoneReports } from '@/data/campaigns'

describe('warzone issue registry', () => {
    it('lists yc128-08 as the latest issue', () => {
        expect(get_latest_issue().slug).toBe('yc128-08')
        expect(get_issue('yc128-08')?.permalink_path).toBe('/warzone/yc128-08/')
        expect(get_issue('yc128-07')?.permalink_path).toBe('/warzone/yc128-07/')
        expect(get_issue_slugs()).toContain('yc128-08')
        expect(get_issue_slugs()).toContain('yc128-07')
        expect(ISSUES).toHaveLength(2)
    })

    it('returns undefined for an unknown slug', () => {
        expect(get_issue('yc128-99')).toBeUndefined()
    })
})

describe('warzone content-hub registration', () => {
    it('nests frontline and economic reports in one Warzone Reports list', () => {
        expect(getWarzoneReports().map((report) => report.slug)).toEqual([
            'yc128-08',
            'amamake-market-yc128-08',
            'yc128-07',
        ])
        expect(getWarzoneReports().every((report) => report.kind === 'warzone')).toBe(true)
        expect(getWarzoneReports().find((report) => report.slug === 'yc128-08')).toMatchObject({
            warzone_type: 'frontline',
        })
        expect(getWarzoneReports().find((report) => report.slug === 'amamake-market-yc128-08')).toMatchObject({
            warzone_type: 'economic',
        })
    })
})
