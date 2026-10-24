import { describe, expect, it } from 'vitest'
import type { FleetParticipants } from '@helpers/api.minmatar.org/fleets'
import {
    event_markers,
    fight_bands,
    in_fleet_chart,
    participants_span,
    roster_orders,
    ship_lane,
    ship_sequence,
    ship_steps,
    short_ship_name,
    span_position,
    time_ticks,
} from '@helpers/fleet_participants'

type Person = FleetParticipants['roster'][number]
type Character = Person['characters'][number]

const at = (minutes: number) => new Date(Date.UTC(2026, 9, 22, 20, 0) + minutes * 60_000).toISOString()

const character = (id: number, name: string, ships: [number, string, number, number][], extra: Partial<Character> = {}): Character => ({
    character_id: id,
    character_name: name,
    joined: at(ships[0][2]),
    left: at(ships[ships.length - 1][3]),
    kills: 0,
    losses: 0,
    lost_at: [],
    ship_type_id: ships[0][0],
    ship_name: ships[0][1],
    ships: ships.map(([ship_type_id, ship_name, start, end]) => ({ ship_type_id, ship_name, start: at(start), end: at(end) })),
    ...extra,
})

const person = (characters: Character[], kills: number): Person => ({
    character_id: characters[0].character_id,
    character_name: characters[0].character_name,
    registered: true,
    joined: characters[0].joined,
    kills,
    losses: 0,
    characters,
})

const spartan = character(1, 'Mini', [
    [73794, 'Thrasher Fleet Issue', 0, 7],
    [670, 'Capsule', 7, 9],
    [73794, 'Thrasher Fleet Issue', 9, 90],
    [24700, 'Myrmidon', 90, 120],
], { ship_type_id: 73794, ship_name: 'Thrasher Fleet Issue', lost_at: [at(7)] })
const late = character(2, 'Late', [[29340, 'Osprey Navy Issue', 96, 120]], { ship_type_id: 29340, ship_name: 'Osprey Navy Issue' })

const participants = {
    in_fleet: [
        { at: at(0), count: 1 },
        { at: at(96), count: 2 },
        { at: at(121), count: 0 },
    ],
    peak: 2,
    peak_at: at(96),
    roster: [person([spartan], 3), person([late], 0)],
} as unknown as FleetParticipants

describe('fleet participants span and chart', () => {
    const span = participants_span(participants)!

    it('covers first join to last seen', () => {
        expect(span.start).toBe(new Date(at(0)).getTime())
        expect(span.end).toBe(new Date(at(121)).getTime())
        expect(span_position(span, at(0))).toBe(0)
        expect(span_position(span, at(121))).toBe(100)
        expect(span_position(span, at(500))).toBe(100)
    })

    it('has no span without anyone in fleet', () => {
        expect(participants_span({ in_fleet: [], roster: [] })).toBeNull()
    })

    it('ticks every half hour in EVE time', () => {
        expect(time_ticks(span).map(tick => tick.label)).toEqual(['20:00', '20:30', '21:00', '21:30', '22:00'])
    })

    it('draws the in-fleet count as steps with headroom over the peak', () => {
        const chart = in_fleet_chart(participants, span)

        expect(chart.y_max).toBe(5)
        expect(chart.line.startsWith('M0.00,80.00 H')).toBe(true)
        expect(chart.area.endsWith('Z')).toBe(true)
        expect(chart.grid.map(line => line.value)).toEqual([])
        expect(chart.peak).toEqual({ left: span_position(span, at(96)), top: 60 })
    })
})

describe('fleet participants lanes', () => {
    const span = participants_span(participants)!

    it('lays out ships along the span, icons only where there is room', () => {
        const lane = ship_lane(spartan, span)

        expect(lane.segments.map(s => s.pod)).toEqual([false, true, false, false])
        expect(lane.segments.map(s => s.icon)).toEqual([true, false, true, true])
        expect(lane.segments[0].title).toBe('Thrasher Fleet Issue 20:00–20:07')
        expect(lane.losses).toEqual([{ left: span_position(span, at(7)), title: '20:07' }])
    })

    it('names the hulls in order without pods or repeats', () => {
        expect(ship_sequence(spartan)).toEqual(['Thrasher Fleet Issue', 'Myrmidon'])
    })

    it('lists every change with short names for phones', () => {
        expect(ship_steps(spartan).map(step => `${step.name} ${step.at}`)).toEqual([
            'Thrasher FI 20:00', 'Capsule 20:07', 'Thrasher FI 20:09', 'Myrmidon 21:30',
        ])
        expect(short_ship_name('Omen Navy Issue')).toBe('Omen NI')
    })

    it('orders people by join, kills and ship', () => {
        expect(roster_orders(participants.roster)).toEqual([
            { joined: 0, kills: 0, ship: 1 },
            { joined: 1, kills: 1, ship: 0 },
        ])
    })
})

describe('fleet participants fights and events', () => {
    const span = participants_span(participants)!

    it('widens a skirmish so it can be clicked and numbers rounds', () => {
        const bands = fight_bands([
            { position: 1, kind: 'round', number: 1, start: at(6), end: at(10), kills: 5, losses: 3 },
            { position: 2, kind: 'skirmish', number: null, start: at(36), end: at(36), kills: 0, losses: 1 },
        ], span)

        expect(bands.map(band => band.label)).toEqual(['1', ''])
        expect(bands[1].width).toBeGreaterThan(0)
        expect(bands.every(band => band.left + band.width <= 100)).toBe(true)
    })

    it('puts a label on the first row it fits and flips it at the right edge', () => {
        const markers = event_markers([
            { kind: 'reship', at: at(4), count: 18, ships: [] },
            { kind: 'reship', at: at(90), count: 10, ships: [] },
            { kind: 'joined', at: at(96), count: 12, ships: [] },
        ], span, ['x'.repeat(60), 'x'.repeat(50), 'x'.repeat(10)])

        expect(markers.map(marker => [marker.at, marker.row, marker.flip])).toEqual([
            ['20:04', 0, false],
            ['21:30', 1, true],
            ['21:36', 0, false],
        ])
    })
})
