import { describe, expect, it } from 'vitest'

import { ui } from '@i18n/ui'
import {
    TRIBE_ACTIVITY_BY_CODE,
    fill_template,
    showcase_period_key,
} from '@helpers/tribe_activity'

const t = (key: keyof typeof ui['en']) => ui.en[key]

const NEW_GROUPS = [
    'supply.market',
    'supply.loyalty-points',
    'pulse.advocates',
    'pulse.readiness',
    'pulse.technology',
    'pulse.thinkspeak',
    'pulse.tournaments',
    'pulse.fishermen',
]

describe('tribe activity specs', () => {
    it('gives every new group four labelled cards and a block', () => {
        for (const code of NEW_GROUPS) {
            const spec = TRIBE_ACTIVITY_BY_CODE[code]
            const metrics = spec.metrics(t, {}, {})
            expect(metrics, code).toHaveLength(4)
            expect(metrics.every((m) => m.label), code).toBe(true)
            expect(spec.block, code).toBeTruthy()
        }
    })

    it('marks only data we do not have as coming soon', () => {
        const soon = (code: string) => TRIBE_ACTIVITY_BY_CODE[code]
            .metrics(t, {}, {})
            .filter((m) => m.coming_soon)
            .map((m) => m.label)

        expect(soon('pulse.readiness')).toEqual(['Doctrine-ready pilots', 'Newly ready'])
        expect(soon('pulse.tournaments')).toHaveLength(4)
        expect(TRIBE_ACTIVITY_BY_CODE['pulse.tournaments'].coming_soon).toBe(true)
        for (const code of NEW_GROUPS.filter((c) => !['pulse.readiness', 'pulse.tournaments'].includes(c)))
            expect(soon(code), code).toEqual([])
    })

    it('formats totals and the best month', () => {
        const [fits_sold, isk] = TRIBE_ACTIVITY_BY_CODE['supply.market'].metrics(
            t,
            { fits_sold: 1635, isk_sold: 360_870_260_929 },
            { best_month: { month: '2026-02', value: 1077 } },
        )
        expect(fits_sold.value).toBe('1,635')
        expect(fits_sold.hint).toBe('Best month: 1,077')
        expect(isk.value).toBe('360.9B')
    })

    it('tracks progress to the next market milestone', () => {
        const all_time = TRIBE_ACTIVITY_BY_CODE['supply.market'].all_time!(t, {
            all_time: { fits_sold: 14483, next_milestone: 25000 },
        })
        expect(all_time?.headline).toBe('14,483 fits sold')
        expect(all_time?.detail).toBe('10,517 to go until 25,000')
        expect(all_time?.progress).toBeCloseTo(0.579, 3)
    })

    it('skips the all-time banner without highlights', () => {
        expect(TRIBE_ACTIVITY_BY_CODE['pulse.fishermen'].all_time!(t, {})).toBeNull()
    })

    it('formats contributor rows from their values', () => {
        const contributors = TRIBE_ACTIVITY_BY_CODE['pulse.readiness'].contributors!(t)
        const values = { doctrine_changes: 3, changes_proposed: 2, changes_reviewed: 1 }
        expect(contributors.value(values)).toBe('3')
        expect(contributors.detail!(values)).toBe('2 proposed · 1 reviewed')
    })
})

describe('fill_template', () => {
    it('replaces every placeholder', () => {
        expect(fill_template('{a} and {a} then {b}', { a: '1', b: '2' })).toBe('1 and 1 then 2')
    })
})

describe('showcase_period_key', () => {
    it('labels ninety-day showcases', () => {
        expect(showcase_period_key('90d')).toBe('tribes.showcase.last_90d')
        expect(showcase_period_key('30d')).toBe('tribes.showcase.last_30d')
        expect(showcase_period_key(undefined)).toBe('tribes.showcase.last_30d')
    })
})
