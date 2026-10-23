/**
 * Geometry and wording for the finished fleet's Participants tab: the
 * in-fleet chart, the fight bands on it, and each pilot's ship lane along
 * the same time axis. Pure functions over the /participants payload, so the
 * tab renders on the server.
 */
import type { FleetParticipants } from '@helpers/api.minmatar.org/fleets'
import { eve_clock } from '@helpers/fleet_fights'

type Person = FleetParticipants['roster'][number]
type Character = Person['characters'][number]
type Fight = FleetParticipants['fights'][number]
type FleetEvent = FleetParticipants['fleet_events'][number]

const MINUTE_MS = 60 * 1000
const CAPSULE_TYPE_IDS = new Set([670, 33328])
/** A ship needs this share of the lane before its icon is drawn. */
const ICON_MIN_WIDTH = 2.5
/** Fight bands narrower than this are widened so they can be clicked. */
const BAND_MIN_WIDTH = 0.8

export interface Span {
    start:  number;
    end:    number;
}

export interface LaneSegment {
    left:           number;
    width:          number;
    pod:            boolean;
    ship_type_id:   number;
    title:          string;
    /** Draw the ship's icon where it starts. */
    icon:           boolean;
}

export interface LaneMark {
    left:   number;
    title:  string;
}

export interface ShipStep {
    ship_type_id:   number;
    name:           string;
    at:             string;
    pod:            boolean;
}

export interface FightBand {
    position:   number;
    left:       number;
    width:      number;
    /** The round's number, or empty for a skirmish. */
    label:      string;
    round:      boolean;
}

export interface EventMarker {
    left:   number;
    at:     string;
    /** The label's row above the chart, so neighbours do not collide. */
    row:    number;
    /** Labels on the right half of the chart run leftwards from the line. */
    flip:   boolean;
}

export interface InFleetChart {
    line:       string;
    area:       string;
    y_max:      number;
    grid:       { value: number, top: number }[];
    peak:       { left: number, top: number } | null;
}

export const is_pod = (ship_type_id: number) => CAPSULE_TYPE_IDS.has(ship_type_id)

/** "Thrasher Fleet Issue" → "Thrasher FI", for tight phone rows. */
export const short_ship_name = (name: string) =>
    name.replace(/ Fleet Issue$/, ' FI').replace(/ Navy Issue$/, ' NI')

const ms = (moment: string | Date) => new Date(moment).getTime()

/** The time the chart and every lane cover: first join to last seen. */
export function participants_span(participants: Pick<FleetParticipants, 'in_fleet' | 'roster'>): Span | null {
    const moments = [
        ...participants.in_fleet.map(point => ms(point.at)),
        ...participants.roster.flatMap(person => person.characters.flatMap(c => [ms(c.joined), ms(c.left)])),
    ]
    if (moments.length === 0) return null
    const start = Math.min(...moments)
    const end = Math.max(...moments)
    return { start, end: Math.max(end, start + MINUTE_MS) }
}

/** Where a moment falls along the span, in percent. */
export function span_position(span: Span, moment: string | Date | number): number {
    const at = typeof moment === 'number' ? moment : ms(moment)
    return Math.min(100, Math.max(0, 100 * (at - span.start) / (span.end - span.start)))
}

/** Half-hour ticks in EVE time, hourly once the fleet ran past four hours. */
export function time_ticks(span: Span): { label: string, left: number }[] {
    const step = (span.end - span.start > 4 * 60 * MINUTE_MS ? 60 : 30) * MINUTE_MS
    const ticks: { label: string, left: number }[] = []
    for (let at = Math.ceil(span.start / step) * step; at <= span.end; at += step) {
        ticks.push({ label: eve_clock(new Date(at)), left: span_position(span, at) })
    }
    return ticks
}

/** A step line of characters in fleet, drawn in a 1000 × 100 box. */
export function in_fleet_chart(
    participants: Pick<FleetParticipants, 'in_fleet' | 'peak' | 'peak_at'>,
    span: Span,
): InFleetChart {
    const y_max = Math.max(5, Math.ceil(participants.peak * 1.15 / 5) * 5)
    const y = (count: number) => 100 - 100 * count / y_max
    const x = (moment: string) => 10 * span_position(span, moment)
    let line = ''
    let last_y = 100
    participants.in_fleet.forEach((point, index) => {
        const px = x(point.at).toFixed(2)
        const py = y(point.count).toFixed(2)
        line += index === 0 ? `M${px},${py}` : ` H${px} V${py}`
        last_y = Number(py)
    })
    if (line) line += ` H1000 V${last_y}`
    const area = line ? `${line} V100 H${x(participants.in_fleet[0].at).toFixed(2)} Z` : ''
    const step = y_max > 40 ? 20 : y_max > 20 ? 10 : 5
    const grid: { value: number, top: number }[] = []
    for (let value = step; value < y_max; value += step) grid.push({ value, top: y(value) })
    const peak = participants.peak_at ?
        { left: span_position(span, participants.peak_at), top: y(participants.peak) } :
        null
    return { line, area, y_max, grid, peak }
}

/** Every round and skirmish as a band on the chart and the lanes. */
export function fight_bands(fights: Fight[], span: Span): FightBand[] {
    return fights.map(fight => {
        const left = span_position(span, fight.start)
        const width = Math.max(BAND_MIN_WIDTH, span_position(span, fight.end) - left)
        return {
            position: fight.position,
            left: Math.min(left, 100 - width),
            width,
            label: fight.kind === 'round' && fight.number ? fight.number.toString() : '',
            round: fight.kind === 'round',
        }
    })
}

/**
 * Join and reship waves as markers above the chart. Each label goes on the
 * first of ``rows`` rows where it does not run into the one before it, its
 * width estimated from its length (``char_width`` percent per character);
 * a label that would run off the right edge runs leftwards instead.
 */
export function event_markers(events: FleetEvent[], span: Span, labels: string[], char_width = 1, rows = 3): EventMarker[] {
    const row_ends: number[] = Array(rows).fill(-Infinity)
    return events.map((event, index) => {
        const left = span_position(span, event.at)
        const width = (labels[index] ?? '').length * char_width
        const flip = left + width > 100
        const from = flip ? left - width : left
        let row = row_ends.findIndex(end => end < from)
        if (row === -1) row = row_ends.indexOf(Math.min(...row_ends))
        row_ends[row] = flip ? left : left + width
        return { left, at: eve_clock(event.at), row, flip }
    })
}

/** A character's ships along the span: pods hatched, icons where a ship starts. */
export function ship_lane(character: Character, span: Span): { segments: LaneSegment[], losses: LaneMark[] } {
    const segments = character.ships.map(ship => {
        const left = span_position(span, ship.start)
        const width = Math.max(0.3, span_position(span, ship.end) - left)
        const pod = is_pod(ship.ship_type_id)
        return {
            left,
            width,
            pod,
            ship_type_id: ship.ship_type_id,
            title: `${ship.ship_name} ${eve_clock(ship.start)}–${eve_clock(ship.end)}`,
            icon: !pod && width >= ICON_MIN_WIDTH,
        }
    })
    const losses = (character.lost_at ?? []).map(at => ({ left: span_position(span, at), title: eve_clock(at) }))
    return { segments, losses }
}

/** Hull names in the order flown, pods and repeats left out. */
export function ship_sequence(character: Character): string[] {
    const names: string[] = []
    for (const ship of character.ships) {
        if (is_pod(ship.ship_type_id)) continue
        if (names[names.length - 1] !== ship.ship_name) names.push(ship.ship_name)
    }
    return names.length > 0 ? names : [character.ship_name]
}

/** Each ship change with its EVE time, for rows too narrow for a lane. */
export function ship_steps(character: Character): ShipStep[] {
    return character.ships.map(ship => ({
        ship_type_id: ship.ship_type_id,
        name: short_ship_name(ship.ship_name),
        at: eve_clock(ship.start),
        pod: is_pod(ship.ship_type_id),
    }))
}

export type RosterOrder = 'joined' | 'kills' | 'ship'

/** Each person's place under every order the roster offers. */
export function roster_orders(roster: Person[]): Record<RosterOrder, number>[] {
    const rank = (compare: (a: number, b: number) => number) => {
        const indexes = roster.map((_, index) => index).sort(compare)
        const places: number[] = []
        indexes.forEach((index, place) => { places[index] = place })
        return places
    }
    const by_kills = rank((a, b) => (roster[b].kills ?? 0) - (roster[a].kills ?? 0) || a - b)
    const by_ship = rank((a, b) => roster[a].characters[0].ship_name.localeCompare(roster[b].characters[0].ship_name) || a - b)
    return roster.map((_, index) => ({ joined: index, kills: by_kills[index], ship: by_ship[index] }))
}
