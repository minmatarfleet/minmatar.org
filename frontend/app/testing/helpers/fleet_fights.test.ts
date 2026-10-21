import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import type { FleetFights } from '@helpers/api.minmatar.org/fleets'
import {
    chart_bands,
    chart_bars,
    chart_position,
    chart_ticks,
    earlier_rounds,
    round_bars,
    round_opponents,
    move_to_side,
    killmail_engagement,
    pilot_odds,
    round_window,
    scope_params,
    strip_bars,
    strip_position,
    strip_ticks,
} from '@helpers/fleet_fights'

const contract = (name: string): FleetFights =>
    JSON.parse(readFileSync(`testing/contracts/${name}.json`, 'utf8'))

const labels = { round: (number: number) => `Round ${number}`, skirmish: 'S' }

describe('fleet fights chart', () => {
    const fights = contract('fleet_fights_finished')
    const chart = fights.chart!

    it('scales bars to the busiest minute', () => {
        const bars = chart_bars(chart)
        expect(bars).toHaveLength(chart.bins.length)
        expect(Math.max(...bars.map(bar => Math.max(bar.up, bar.down)))).toBe(1)
    })

    it('places each round where it happened, in order', () => {
        const bands = chart_bands(chart, fights.rounds, labels, false)
        expect(bands.map(band => band.label)).toEqual(['Round 1', 'Round 2'])
        expect(bands[0].left).toBeLessThan(bands[1].left)
        bands.forEach(band => {
            expect(band.left + band.width).toBeLessThanOrEqual(100.0001)
            expect(band.width).toBeGreaterThan(0)
        })
    })

    it('clamps positions to the chart', () => {
        expect(chart_position(chart, '2000-01-01T00:00:00Z')).toBe(0)
        expect(chart_position(chart, '2100-01-01T00:00:00Z')).toBe(100)
    })

    it('ticks every 15 minutes on a short fleet', () => {
        const ticks = chart_ticks(chart)
        expect(ticks.length).toBeGreaterThan(0)
        ticks.forEach(tick => expect(Number(tick.label.slice(3))).toSatisfy((m: number) => m % 15 === 0))
    })
})

describe('fleet fights rounds', () => {
    it('stretches the live round to the right edge', () => {
        const fights = contract('fleet_fights_live')
        const bands = chart_bands(fights.chart!, fights.rounds, labels, true)
        const last = bands[bands.length - 1]
        expect(last.live).toBe(true)
        expect(last.left + last.width).toBeCloseTo(100, 3)
    })

    it('lists earlier rounds newest first', () => {
        const fights = contract('fleet_fights_live')
        expect(earlier_rounds(fights).map(round => round.number)).toEqual([1])
    })

    it('counts ships, not pods, in a round per minute', () => {
        const round = contract('fleet_fights_finished').rounds[0]
        const bars = round_bars(round)
        expect(bars.reduce((sum, bar) => sum + bar.kills, 0)).toBe(round.ships_destroyed)
        expect(bars.reduce((sum, bar) => sum + bar.losses, 0)).toBe(round.ships_lost)
    })

    it('names who the round was against', () => {
        expect(round_opponents(contract('fleet_fights_finished').rounds[0]).map(group => group.name)).toEqual(['Hostile Alliance'])
    })
})

describe('round bars for a live round', () => {
    it('stop ten minutes past the last mail however late the page is', () => {
        const round = contract('fleet_fights_live').rounds.at(-1)!
        const bars = round_bars(round, '2030-01-01T00:00:00Z')
        expect(bars.length).toBeLessThanOrEqual(round.minutes + 11)
        expect(bars.reduce((sum, bar) => sum + bar.kills, 0)).toBe(round.ships_destroyed)
    })
})

describe('battle report sides', () => {
    it('moves a group and keeps the others, sorted by id', () => {
        expect(move_to_side('99000002:0', 98000001, 2)).toBe('98000001:2,99000002:0')
    })

    it('moves a group again instead of listing it twice', () => {
        expect(move_to_side('98000001:2,99000002:0', 98000001, 1)).toBe('98000001:1,99000002:0')
    })

    it('ignores junk and a missing move', () => {
        expect(move_to_side('x:1,99000002:-1,5', NaN, NaN)).toBe('')
    })
})

describe('killmail engagement', () => {
    const rounds = contract('fleet_fights_finished').rounds
    const first = rounds.find((round: any) => round.kind === 'round')!

    it('tags a mail inside an engagement with its number', () => {
        expect(killmail_engagement(first.start, rounds)).toBe(first.number)
    })

    it('leaves a mail far from every engagement untagged', () => {
        expect(killmail_engagement('2001-01-01T00:00:00Z', rounds)).toBeNull()
    })
})

describe('pilot odds', () => {
    it('says who had the numbers, to one decimal', () => {
        expect(pilot_odds(50, 150)).toEqual({ side: 'outnumbered', ratio: 3 })
        expect(pilot_odds(40, 25)).toEqual({ side: 'outnumbering', ratio: 1.6 })
    })

    it('calls close numbers even', () => {
        expect(pilot_odds(30, 34)).toEqual({ side: 'even', ratio: 1 })
    })

    it('has nothing to say without both sides', () => {
        expect(pilot_odds(30, 0)).toBeNull()
        expect(pilot_odds(null, 12)).toBeNull()
        expect(pilot_odds(30, undefined)).toBeNull()
    })
})

describe('battle report scope', () => {
    it('pads an engagement a minute each side', () => {
        expect(round_window({ start: '2026-10-18T18:27:12Z', end: '2026-10-18T18:48:47Z' })).toEqual({
            start: '2026-10-18T18:26:12.000Z',
            end: '2026-10-18T18:49:47.000Z',
        })
    })

    it('prefers a segment to a window and keeps the sides', () => {
        expect(scope_params({ start: 'a', end: 'b', segment: 4, sides: '9:1' })).toEqual({ segment: '4', sides: '9:1' })
        expect(scope_params({ start: 'a', end: 'b' })).toEqual({ start: 'a', end: 'b' })
        expect(scope_params({ start: 'a' })).toEqual({})
    })
})

describe('battle report activity strip', () => {
    const report = {
        span_start: '2026-10-18T18:00:00Z',
        span_end: '2026-10-18T18:10:00Z',
        activity: [
            { minute: '2026-10-18T18:01:00Z', isk: [300, 100, 0] },
            { minute: '2026-10-18T18:05:00Z', isk: [0, 100, 0] },
        ],
    }

    it('places moments along the span and clamps the ends', () => {
        expect(strip_position(report, '2026-10-18T18:05:00Z')).toBe(50)
        expect(strip_position(report, '2026-10-18T17:00:00Z')).toBe(0)
        expect(strip_position(report, '2026-10-18T19:00:00Z')).toBe(100)
    })

    it('stacks each minute by team and scales to the busiest', () => {
        const bars = strip_bars(report)
        expect(bars).toHaveLength(2)
        expect(bars[0].height).toBe(1)
        expect(bars[1].height).toBeCloseTo(0.5)
        expect(bars[0].parts).toEqual([{ team: 0, share: 0.75 }, { team: 1, share: 0.25 }])
        expect(bars[0].left).toBeGreaterThan(10)
        expect(bars[0].left + bars[0].width).toBeLessThan(20)
    })

    it('ticks every quarter hour in EVE time', () => {
        expect(strip_ticks({ span_start: '2026-10-18T17:10:00Z', span_end: '2026-10-18T18:05:00Z' }).map(tick => tick.label))
            .toEqual(['17:15', '17:30', '17:45', '18:00'])
    })
})
