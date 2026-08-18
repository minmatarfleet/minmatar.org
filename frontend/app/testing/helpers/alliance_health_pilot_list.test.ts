import { describe, expect, it } from 'vitest'
import {
    apply_list_metric_tones,
    compare_health_sort_values,
    csv_from_matrix,
    default_health_order_dir,
    format_metric_typical,
    health_confidence_label,
    health_pilot_card_id,
    next_health_order_state,
    paged_health_list_rows,
    tone_vs_median,
} from '@helpers/alliance_health_pilot_list'

describe('alliance_health_pilot_list', () => {
    it('defaults numbers descending and names ascending', () => {
        expect(default_health_order_dir('number')).toBe('desc')
        expect(default_health_order_dir('text')).toBe('asc')
    })

    it('toggles direction on the same chip', () => {
        expect(
            next_health_order_state('fleets', 'desc', 'fleets', { fleets: 'number' }),
        ).toEqual({ order_by: 'fleets', order_dir: 'asc' })
    })

    it('switches chip to the kind default', () => {
        expect(
            next_health_order_state('fleets', 'desc', 'name', {
                fleets: 'number',
                name: 'text',
            }),
        ).toEqual({ order_by: 'name', order_dir: 'asc' })
    })

    it('sorts missing numbers last', () => {
        expect(compare_health_sort_values('', '3', 'number', 'desc')).toBe(1)
        expect(compare_health_sort_values('3', '', 'number', 'asc')).toBe(-1)
    })

    it('sorts numbers by the requested direction', () => {
        expect(compare_health_sort_values('2', '10', 'number', 'desc')).toBe(1)
        expect(compare_health_sort_values('2', '10', 'number', 'asc')).toBe(-1)
    })

    it('marks double the median as good when higher is better', () => {
        expect(tone_vs_median(18, 6, 'higher')).toBe('good')
        expect(tone_vs_median(2, 6, 'higher')).toBe('bad')
        expect(tone_vs_median(7, 6, 'higher')).toBeUndefined()
    })

    it('inverts tone when lower is better', () => {
        expect(tone_vs_median(40, 10, 'lower')).toBe('bad')
        expect(tone_vs_median(3, 10, 'lower')).toBe('good')
    })

    it('treats any activity as good when the median is zero', () => {
        expect(tone_vs_median(18, 0, 'higher')).toBe('good')
        expect(tone_vs_median(0, 0, 'higher')).toBeUndefined()
    })

    it('keeps hour units on typical labels', () => {
        expect(format_metric_typical('6h', 4.5)).toBe('4.5h')
    })

    it('colors a list from its own median', () => {
        const colored = apply_list_metric_tones([
            {
                name: 'a',
                corp: 'x',
                search_text: 'a',
                metrics: [{ id: 'voice', label: 'Voice', value: '18h', sort: 18 }],
            },
            {
                name: 'b',
                corp: 'x',
                search_text: 'b',
                metrics: [{ id: 'voice', label: 'Voice', value: '6h', sort: 6 }],
            },
            {
                name: 'c',
                corp: 'x',
                search_text: 'c',
                metrics: [{ id: 'voice', label: 'Voice', value: '2h', sort: 2 }],
            },
        ])
        expect(colored[0].metrics[0].tone).toBe('good')
        expect(colored[0].metrics[0].typical).toBe('6h')
        expect(colored[1].metrics[0].tone).toBeUndefined()
        expect(colored[2].metrics[0].tone).toBe('bad')
    })

    it('labels confidence as high/medium/low confidence', () => {
        const t = (key: string) =>
            ({
                'alliance.health.conf.high': 'high confidence',
                'alliance.health.conf.medium': 'medium confidence',
                'alliance.health.conf.low': 'low confidence',
            })[key] ?? key
        expect(health_confidence_label('high', t)).toBe('high confidence')
        expect(health_confidence_label('medium', t)).toBe('medium confidence')
        expect(health_confidence_label('low', t)).toBe('low confidence')
        expect(health_confidence_label('—', t)).toBeNull()
        expect(health_confidence_label(undefined, t)).toBeNull()
    })

    it('builds unique card ids per section', () => {
        expect(health_pilot_card_id('attention', 42)).toBe('alliance-health-attention-42')
        expect(health_pilot_card_id('trials', 42)).toBe('alliance-health-trials-42')
    })

    it('pages the same corp-filtered fleet order Alpine uses', () => {
        const row = (
            name: string,
            corp: string,
            fleets: number,
        ) => ({
            name,
            corp,
            search_text: name.toLowerCase(),
            metrics: [{ id: 'fleets', label: 'Fleets', value: String(fleets), sort: fleets }],
        })
        const page = paged_health_list_rows(
            [
                row('low', 'home', 2),
                row('high', 'home', 40),
                row('other', 'away', 99),
                row('mid', 'home', 10),
            ],
            {
                corp: 'home',
                order_by: 'fleets',
                order_dir: 'desc',
                order_kinds: { fleets: 'number' },
                page: 1,
                page_size: 2,
            },
        )
        expect(page.map((item) => item.name)).toEqual(['high', 'mid'])
    })

    it('escapes CSV fields and builds a matrix', () => {
        expect(csv_from_matrix([
            ['Pilot', 'Corp'],
            ['Kayra, Nathuul', 'Banshee Squadron'],
        ])).toBe('Pilot,Corp\n"Kayra, Nathuul",Banshee Squadron\n')
    })
})
