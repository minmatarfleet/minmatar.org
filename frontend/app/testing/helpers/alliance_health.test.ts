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
    it('shows promote whenever the officer can act on the corp', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                corporation_id: 1,
            }),
        ).toBe(true)
    })

    it('shows promote for officers scoped to that corp', () => {
        expect(
            can_promote_alliance_health_trial({
                can_mutate: true,
                alliance_wide: false,
                officer_corp_ids: [7],
                corporation_id: 7,
            }),
        ).toBe(true)
    })

    it('hides promote for a corp the officer cannot act on', () => {
        expect(
            can_promote_alliance_health_trial({
                can_mutate: true,
                alliance_wide: false,
                officer_corp_ids: [7],
                corporation_id: 9,
            }),
        ).toBe(false)
    })

    it('requires mutate permission', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                can_mutate: false,
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
