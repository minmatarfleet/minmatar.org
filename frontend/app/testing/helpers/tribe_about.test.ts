import { describe, expect, it } from 'vitest'
import type { TribeAboutGroup, TribeGroupAbout } from '@dtypes/api.minmatar.org'
import {
    SUPPLY_FLOW,
    TRIBE_ABOUT_STAGES,
    group_about_vitals,
    group_has_year,
    month_long,
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

describe('group About vitals', () => {
    const t = (key: string) => ({
        'tribes.about.group.members': 'Members',
        'tribes.about.group.joined': 'Joined',
        'tribes.about.group.joined_detail': 'last 90 days',
        'tribes.about.group.other_groups': 'Also in other {tribe} groups',
        'tribes.about.corporations': 'Corporations',
    } as Record<string, string>)[key] ?? key

    const about: TribeGroupAbout = {
        group_id: 5,
        tribe_id: 1,
        code: 'capitals.dreads',
        ready: true,
        generated_at: null,
        period_start: null,
        period_end: null,
        people: 1234,
        joined_recent: 40,
        in_other_groups: 12,
        growth: { months: [], counts: [] },
        corporations: [],
        corporation_count: 9,
        year: null,
        capitals: null,
        supply: null,
    }

    it('shows only the headcount until the year is built', () => {
        expect(group_about_vitals(t, null, 7, 'Capitals')).toEqual([{ value: '7', label: 'Members' }])
        expect(group_about_vitals(t, { ...about, ready: false }, 7, 'Capitals')).toHaveLength(1)
    })

    it('names the tribe and counts from the year once built', () => {
        const vitals = group_about_vitals(t, about, 7, 'Capitals')

        expect(vitals.map((vital) => vital.label)).toEqual([
            'Members',
            'Joined',
            'Also in other Capitals groups',
            'Corporations',
        ])
        expect(vitals[0].value).toBe('1,234')
        expect(vitals[1].detail).toBe('last 90 days')
    })

    it('writes a best month out in full', () => {
        expect(month_long('2026-03', 'en')).toBe('March 2026')
    })
})
