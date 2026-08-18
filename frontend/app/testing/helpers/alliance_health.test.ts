import { describe, expect, it } from 'vitest'
import { can_promote_alliance_health_trial } from '@helpers/api.minmatar.org/alliance_health'

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

    it('shows promote on passing when tenure is unknown', () => {
        expect(
            can_promote_alliance_health_trial({
                ...base,
                bucket: 'passing',
                decision: null,
                alliance_days: null,
            }),
        ).toBe(true)
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
