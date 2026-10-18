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
    round_groups,
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
        expect(round_groups(contract('fleet_fights_finished').rounds[0])).toEqual(['Hostile Alliance'])
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
