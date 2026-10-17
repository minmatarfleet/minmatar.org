import { describe, expect, it } from 'vitest'
import type { TribeAboutGroup } from '@dtypes/api.minmatar.org'
import {
    SUPPLY_FLOW,
    TRIBE_ABOUT_STAGES,
    group_has_year,
    order_groups,
    trim_leading_zeros,
} from '@helpers/tribe_about'

function group(code: string, name: string, totals: Record<string, number> = {}, manual = false): TribeAboutGroup {
    return {
        id: name.length,
        code,
        name,
        member_count: 1,
        manual,
        totals,
        highlights: {},
        top_pilots: [],
    }
}

describe('tribe About helpers', () => {
    it('puts Supply groups in the order work moves down the line', () => {
        const groups = [
            group('supply.market', 'Market'),
            group('supply.extra', 'Archive'),
            group('supply.mining', 'Mining'),
            group('supply.freighters', 'Freighters'),
        ]
        expect(order_groups(groups, SUPPLY_FLOW).map((g) => g.name)).toEqual([
            'Mining',
            'Freighters',
            'Market',
            'Archive',
        ])
    })

    it('treats manual groups and all-zero totals as having no year to show', () => {
        expect(group_has_year(group('pulse.tournaments', 'Tournaments', {}, true))).toBe(false)
        expect(group_has_year(group('supply.market', 'Market', { fits_sold: 0 }))).toBe(false)
        expect(group_has_year(group('supply.market', 'Market', { fits_sold: 3 }))).toBe(true)
    })

    it('starts charts at the first month with data', () => {
        const rows = [{ v: 0 }, { v: 0 }, { v: 4 }, { v: 0 }, { v: 2 }]
        expect(trim_leading_zeros(rows, (row) => row.v)).toEqual([{ v: 4 }, { v: 0 }, { v: 2 }])
        expect(trim_leading_zeros([{ v: 0 }], (row) => row.v)).toEqual([])
    })

    it('adds Thinkspeak posts and videos into one stories number', () => {
        const stage = TRIBE_ABOUT_STAGES['pulse.thinkspeak']
        expect(stage.value({ posts_published: 59, videos: 58 })).toBe('117')
    })

    it('gives every stage a headline that never prints NaN', () => {
        for (const stage of Object.values(TRIBE_ABOUT_STAGES))
            expect(stage.value({})).not.toContain('NaN')
    })
})
