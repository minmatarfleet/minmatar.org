import { describe, expect, it } from 'vitest'
import {
    alliance_health_corp_options,
    alliance_health_counts_for_corp,
    can_promote_alliance_health_trial,
} from '@helpers/api.minmatar.org/alliance_health'

const base = {
    can_mutate: true,
    alliance_wide: true,
    officer_corp_ids: [] as number[],
    corporation_id: 1,
}

describe('can_promote_alliance_health_trial', () => {
    it('shows promote on the default current tab for approve decisions', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                bucket: 'current',
                decision: 'approve',
                alliance_days: 70,
            }),
        ).toBe(true)
    })

    it('hides promote on current for people who are not approve-ready', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                bucket: 'current',
                decision: 'nudge',
                alliance_days: 80,
            }),
        ).toBe(false)
    })

    it('shows promote on evaluating for people who are not passing yet', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                bucket: 'evaluating',
                decision: 'nudge',
                alliance_days: 80,
            }),
        ).toBe(true)
        expect(
            can_promote_alliance_health_trial({
                ...base,
                bucket: 'evaluating',
                decision: 'hold',
                alliance_days: 90,
            }),
        ).toBe(true)
    })

    it('hides promote on evaluating for too-early tenure', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                bucket: 'evaluating',
                decision: 'too_early',
                alliance_days: 20,
            }),
        ).toBe(false)
    })

    it('hides promote on passing when tenure is under 60 days', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                bucket: 'passing',
                decision: null,
                alliance_days: 40,
            }),
        ).toBe(false)
        expect(
            can_promote_alliance_health_trial({
                ...base,
                bucket: 'passing',
                decision: null,
                alliance_days: null,
            }),
        ).toBe(false)
    })

    it('hides promote for too-early pilots on passing', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                bucket: 'passing',
                decision: 'too_early',
                alliance_days: 20,
            }),
        ).toBe(false)
    })

    it('requires mutate permission', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                can_mutate: false,
                bucket: 'passing',
                decision: 'approve',
                alliance_days: 70,
            }),
        ).toBe(false)
    })
})

describe('alliance_health_counts_for_corp', () => {
    const all = { fading: 4, dark: 2, seasonal: 1 }
    const by_corp = {
        all,
        FOSFO: { fading: 1, dark: 0, seasonal: 1 },
    }

    it('uses the selected corp tab totals', () => {
        expect(alliance_health_counts_for_corp(all, by_corp, 'FOSFO')).toEqual({
            fading: 1,
            dark: 0,
            seasonal: 1,
        })
    })

    it('keeps alliance totals for all corporations', () => {
        expect(alliance_health_counts_for_corp(all, by_corp, 'all')).toEqual(all)
    })

    it('zeros a corp that is not in the map', () => {
        expect(alliance_health_counts_for_corp(all, by_corp, 'TDT')).toEqual({
            fading: 0,
            dark: 0,
            seasonal: 0,
        })
    })

    it('lists corps from the count map', () => {
        expect(alliance_health_corp_options(by_corp, ['TDT'])).toEqual(['FOSFO', 'TDT'])
    })
})
