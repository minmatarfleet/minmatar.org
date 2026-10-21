/**
 * Geometry and wording for the fleet Fights tab: where each round sits on
 * the minute chart, which ticks to draw, and the one-line skirmish summary.
 * Pure functions over the /fights payload, so the tab renders on the server.
 */
import type { FleetFights, FleetFightRound, FleetBattleReport } from '@helpers/api.minmatar.org/fleets'

const MINUTE_MS = 60 * 1000

export interface ChartBar {
    kills:  number;
    losses: number;
    /** Bar heights as a share of the half-chart, 0 to 1. */
    up:     number;
    down:   number;
}

export interface ChartBand {
    index:  number;
    label:  string;
    /** For a band too narrow for its label: "R5" or "S". */
    short:  string;
    kind:   string;
    left:   number;
    width:  number;
    live:   boolean;
}

export interface ChartTick {
    label:  string;
    left:   number;
}

const minutes_between = (start: string, end: string) =>
    (new Date(end).getTime() - new Date(start).getTime()) / MINUTE_MS

export function chart_bars(chart: NonNullable<FleetFights['chart']>): ChartBar[] {
    const peak = chart.bins.reduce((most, [kills, losses]) => Math.max(most, kills, losses), 1)
    return chart.bins.map(([kills, losses]) => ({
        kills,
        losses,
        up: kills / peak,
        down: losses / peak,
    }))
}

/** Percent of the chart's width from its start to ``moment``. */
export function chart_position(chart: NonNullable<FleetFights['chart']>, moment: string): number {
    const total = Math.max(1, minutes_between(chart.start, chart.end))
    return Math.min(100, Math.max(0, 100 * minutes_between(chart.start, moment) / total))
}

export function chart_bands(
    chart: NonNullable<FleetFights['chart']>,
    rounds: FleetFightRound[],
    labels: { round: (number: number) => string, skirmish: string },
    live: boolean,
): ChartBand[] {
    const total = Math.max(1, minutes_between(chart.start, chart.end))
    const one_bin = 100 * chart.bin_minutes / total
    return rounds.map((round, index) => {
        const left = chart_position(chart, round.start)
        const is_live = live && index === rounds.length - 1
        const end = is_live ? 100 : chart_position(chart, round.end) + one_bin
        return {
            index,
            label: round.kind === 'round' ? labels.round(round.number ?? 0) : labels.skirmish,
            short: round.kind === 'round' ? `E${round.number ?? 0}` : labels.skirmish,
            kind: round.kind,
            left,
            width: Math.max(one_bin, Math.min(100, end) - left),
            live: is_live,
        }
    })
}

/** EVE-time ticks every 15, 30 or 60 minutes, whichever keeps about 6–10. */
export function chart_ticks(chart: NonNullable<FleetFights['chart']>): ChartTick[] {
    const total = minutes_between(chart.start, chart.end)
    const step = total <= 180 ? 15 : total <= 360 ? 30 : 60
    const start = new Date(chart.start).getTime()
    const first = Math.ceil(start / (step * MINUTE_MS)) * step * MINUTE_MS
    const ticks: ChartTick[] = []
    for (let at = first; at <= new Date(chart.end).getTime(); at += step * MINUTE_MS) {
        const iso = new Date(at).toISOString()
        ticks.push({ label: iso.slice(11, 16), left: chart_position(chart, iso) })
    }
    return ticks
}

// A live round's bars run on past its last mail by this much, at most.
const LIVE_TAIL_MINUTES = 10
const ROUND_MAX_BARS = 120

/**
 * Ships killed and lost per minute across one round, for its mini chart.
 * ``end`` is when the bars stop: the last mail, or now for a live round
 * (never more than ten minutes past its last mail). A long round gets wider
 * bins so it never has more than 120 bars.
 */
export function round_bars(round: FleetFightRound, end: string = round.end): ChartBar[] {
    const tail = Math.min(LIVE_TAIL_MINUTES, Math.max(0, minutes_between(round.end, end)))
    const span = Math.max(1, Math.floor(minutes_between(round.start, round.end) + tail) + 1)
    const per_bar = Math.ceil(span / ROUND_MAX_BARS)
    const bins = Array.from({ length: Math.ceil(span / per_bar) }, () => [0, 0])
    round.killmails.forEach(row => {
        if (row.pod) return
        const minute = Math.max(0, Math.floor(minutes_between(round.start, row.time)))
        bins[Math.min(bins.length - 1, Math.floor(minute / per_bar))][row.outcome === 'kill' ? 0 : 1] += 1
    })
    return chart_bars({ start: round.start, end, bin_minutes: per_bar, bins })
}

/** Who an engagement was against, most involved first, for GroupLogos. */
export function round_opponents(round: FleetFightRound): { id: number | null, name: string, kind: string | null }[] {
    return round.hostiles
        .filter(hostile => hostile.pilots > 0 || hostile.ships_killed > 0)
        .map(hostile => ({ id: hostile.group_id ?? null, name: hostile.name, kind: hostile.kind ?? null }))
}

export function seconds_since(moment: string, now: Date = new Date()): number {
    return Math.max(0, Math.round((now.getTime() - new Date(moment).getTime()) / 1000))
}

/** Rounds before the latest, newest first: the live tab's "Earlier" list. */
export function earlier_rounds(fights: FleetFights): FleetFightRound[] {
    return fights.rounds.slice(0, -1).reverse()
}

/** Position in the rounds list, 1-based, as used in round report URLs. */
export function round_position(fights: FleetFights, round: FleetFightRound): number {
    return fights.rounds.indexOf(round) + 1
}

/** "18:27" in EVE time (UTC) from an ISO time or a Date. */
export const eve_clock = (moment: string | Date): string => new Date(moment).toISOString().slice(11, 16)

// A mail belongs to an engagement when it lands inside it, give or take this.
const ENGAGEMENT_PAD_MS = 60 * 1000

/** The engagement number a killmail falls in, or null for a skirmish or a quiet spell. */
export function killmail_engagement(time: string, rounds: FleetFightRound[]): number | null {
    const at = new Date(time).getTime()
    const round = rounds.find(round => round.kind === 'round' &&
        new Date(round.start).getTime() - ENGAGEMENT_PAD_MS <= at &&
        at <= new Date(round.end).getTime() + ENGAGEMENT_PAD_MS)
    return round?.number ?? null
}

/**
 * Battle report sides after moving one group: ``sides`` is the report's
 * ``group:team,...`` override string. Ids sort so the same sides always give
 * the same URL.
 */
export function move_to_side(sides: string, group: number, team: number): string {
    const moves = new Map<number, number>()
    for (const pair of sides.split(',')) {
        const [id, index] = pair.split(':').map(Number)
        if (Number.isInteger(id) && id > 0 && Number.isInteger(index) && index >= 0) moves.set(id, index)
    }
    if (Number.isInteger(group) && group > 0 && Number.isInteger(team) && team >= 0) moves.set(group, team)
    return [...moves.entries()].sort((a, b) => a[0] - b[0]).map(([id, index]) => `${id}:${index}`).join(',')
}

/** A round's battle report window: its first mail minus a minute to its last plus a minute. */
export function round_window(round: { start: string, end: string }): { start: string, end: string } {
    return {
        start: new Date(new Date(round.start).getTime() - MINUTE_MS).toISOString(),
        end: new Date(new Date(round.end).getTime() + MINUTE_MS).toISOString(),
    }
}

/** What a battle report covers: the whole fleet, a window, or a saved segment. */
export interface BattleScope {
    start?:     string | null;
    end?:       string | null;
    segment?:   number | null;
    /** Group moves, ``group:team,...``. */
    sides?:     string | null;
}

/** A battle report scope as query params; a segment wins over a window. */
export function scope_params(scope: BattleScope): Record<string, string> {
    const params: Record<string, string> = {}
    if (scope.segment) params.segment = scope.segment.toString()
    else if (scope.start && scope.end) {
        params.start = scope.start
        params.end = scope.end
    }
    if (scope.sides) params.sides = scope.sides
    return params
}

export interface StripBar {
    /** Percent of the strip. */
    left:   number;
    width:  number;
    /** Share of the strip's height, 0 to 1; square root, so small fights still show. */
    height: number;
    /** Each team's share of the bar, in team order. */
    parts:  { team: number, share: number }[];
}

/** Where a moment falls on the activity strip, in percent. */
export function strip_position(report: Pick<FleetBattleReport, 'span_start' | 'span_end'>, moment: string): number {
    const start = new Date(report.span_start).getTime()
    const span = Math.max(1, new Date(report.span_end).getTime() - start)
    return Math.min(100, Math.max(0, 100 * (new Date(moment).getTime() - start) / span))
}

/** One bar per minute of the fleet's activity, stacked by the team that lost the ISK. */
export function strip_bars(report: Pick<FleetBattleReport, 'span_start' | 'span_end' | 'activity'>): StripBar[] {
    const totals = report.activity.map(minute => minute.isk.reduce((sum, isk) => sum + isk, 0))
    const busiest = Math.max(1, ...totals)
    const minute_width = strip_position(report, new Date(new Date(report.span_start).getTime() + MINUTE_MS).toISOString())
    return report.activity.map((minute, index) => ({
        left: strip_position(report, minute.minute) + minute_width * 0.12,
        width: minute_width * 0.76,
        height: Math.max(0.06, Math.sqrt(totals[index] / busiest)),
        parts: minute.isk
            .map((isk, team) => ({ team, share: totals[index] ? isk / totals[index] : 0 }))
            .filter(part => part.share > 0),
    }))
}

/** Quarter-hour ticks along the strip, in EVE time. */
export function strip_ticks(report: Pick<FleetBattleReport, 'span_start' | 'span_end'>): ChartTick[] {
    const quarter = 15 * MINUTE_MS
    const end = new Date(report.span_end).getTime()
    const ticks: ChartTick[] = []
    for (let at = Math.ceil(new Date(report.span_start).getTime() / quarter) * quarter; at <= end; at += quarter) {
        const moment = new Date(at).toISOString()
        ticks.push({ label: eve_clock(moment), left: strip_position(report, moment) })
    }
    return ticks
}

/** Damage the way br.evetools shows it: 108.7k, 1.56m. */
export function format_damage(damage: number): string {
    if (damage >= 1_000_000) return `${(damage / 1_000_000).toFixed(2)}m`
    if (damage >= 1_000) return `${(damage / 1_000).toFixed(1)}k`
    return damage.toString()
}

// Battle report rows sort by hull class, biggest first, like br.evetools.
const SHIP_GROUP_ORDER = [
    'Titan', 'Supercarrier', 'Carrier', 'Force Auxiliary', 'Dreadnought', 'Lancer Dreadnought',
    'Black Ops', 'Marauder', 'Battleship', 'Attack Battlecruiser', 'Command Ship', 'Combat Battlecruiser',
    'Strategic Cruiser', 'Heavy Assault Cruiser', 'Heavy Interdiction Cruiser', 'Logistics', 'Recon Ship',
    'Force Recon Ship', 'Combat Recon Ship', 'Flag Cruiser', 'Cruiser', 'Command Destroyer', 'Tactical Destroyer',
    'Interdictor', 'Destroyer', 'Assault Frigate', 'Logistics Frigate', 'Electronic Attack Ship', 'Stealth Bomber',
    'Covert Ops', 'Interceptor', 'Frigate', 'Shuttle', 'Corvette', 'Capsule',
]

/** Where a hull group sorts in a battle report: lower is bigger. */
export function ship_group_rank(group: string | undefined): number {
    const index = group ? SHIP_GROUP_ORDER.indexOf(group) : -1
    return index === -1 ? SHIP_GROUP_ORDER.length - 1.5 : index
}

export interface PilotOdds {
    side:   'outnumbered' | 'outnumbering' | 'even';
    /** The bigger side per pilot on the smaller, to one decimal: 3 for 150 vs 50. */
    ratio:  number;
}

/** Who had the numbers, from our pilots and the hostiles we fought; null when either is unknown. */
export function pilot_odds(ours: number | null | undefined, theirs: number | null | undefined): PilotOdds | null {
    if (!ours || !theirs) return null
    const ratio = Math.round(10 * Math.max(ours, theirs) / Math.min(ours, theirs)) / 10
    if (ratio < 1.2) return { side: 'even', ratio: 1 }
    return { side: theirs > ours ? 'outnumbered' : 'outnumbering', ratio }
}
