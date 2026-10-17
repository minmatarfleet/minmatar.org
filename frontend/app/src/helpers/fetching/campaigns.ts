import type {
    CampaignListItem,
    CampaignSystemSummary,
    CampaignSystemTrendPoint,
    CampaignCoverageHour,
    CampaignPace,
    CampaignStatusChip,
    CampaignTotals,
    CampaignWeek,
    CampaignWeekProgress,
} from '@dtypes/api.minmatar.org'
import type { TagColors } from '@dtypes/layout_components'
import { get_campaigns } from '@helpers/api.minmatar.org/campaigns'

export interface CampaignGroups {
    live:       CampaignListItem[];
    upcoming:   CampaignListItem[];
    past:       CampaignListItem[];
}

export interface SparklinePoint {
    x:              number;
    y:              number;
    captured_at:    string;
    value:          number;
}

export interface SparklinePath {
    line:   string;
    area:   string;
    empty:  boolean;
    /** One per reading, for hover targets that name the moment and the value. */
    points: SparklinePoint[];
}

export type CampaignTotalsLabelKey =
    | 'campaigns.stat.enlisted'
    | 'campaigns.stat.kills'
    | 'campaigns.stat.losses'
    | 'campaigns.stat.isk_destroyed'
    | 'campaigns.stat.complexes'
    | 'campaigns.stat.advantage_generated'
    | 'campaigns.stat.active_today'
    | 'campaigns.stat.structure_kills'
    | 'campaigns.stat.capital_kills'
    | 'campaigns.stat.structures_destroyed'
    | 'campaigns.stat.structures_remaining'

export interface CampaignTotalsStat {
    label:  string;
    value:  string;
}

export interface CoverageBar {
    hour:               number;
    our_active_days:    number;
    hostile_activity:   number;
    our_percent:        number;
    hostile_percent:    number;
}

/** A fleet can only be attached to a campaign that is open for fights. */
const ATTACHABLE_CAMPAIGN_STATUSES = [ 'scheduled', 'active' ]

/**
 * Id/name/slug only — the campaign dropdown on the fleet schedule form.
 *
 * Scheduling a fleet must never depend on campaigns: a fleet commander
 * without the `campaigns.view` feature gets a 403 here, and every other
 * failure (backend down, network) is just as survivable. Both answer with an
 * empty list so the form renders without the field.
 */
export async function fetch_campaign_options(access_token:string | false = false):Promise<CampaignListItem[]> {
    try {
        const campaigns = await get_campaigns(access_token)

        return (campaigns ?? []).filter(campaign => ATTACHABLE_CAMPAIGN_STATUSES.includes(campaign.status))
    } catch (error) {
        console.log(`Skipping campaign options: ${error.message}`)

        return []
    }
}

/** Live campaigns first, then the ones yet to open, then everything finished. */
export const group_campaigns = (campaigns:CampaignListItem[]):CampaignGroups => {
    return {
        live: campaigns.filter(campaign => campaign.status === 'active'),
        upcoming: campaigns.filter(campaign => campaign.status === 'scheduled' || campaign.status === 'draft'),
        past: campaigns.filter(campaign => campaign.status === 'completed' || campaign.status === 'archived'),
    }
}

/** Most contested system first so the fight that needs people leads the list. */
/** EVE faction ids for the two warzone militias. */
export const MINMATAR_FACTION_ID = 500002
export const AMARR_FACTION_ID = 500003

/**
 * Who holds the system right now: ESI occupier, falling back to owner.
 * Matches warzone occupancy (holder = live ESI occupier).
 */
export const holder_faction_id = (
    system: { occupier_faction_id?: number | null; owner_faction_id?: number | null } | null | undefined,
): number | null => {
    if (!system) return null

    return system.occupier_faction_id ?? system.owner_faction_id ?? null
}

export const holder_militia = (
    system: { occupier_faction_id?: number | null; owner_faction_id?: number | null } | null | undefined,
): 'minmatar' | 'amarr' | null => {
    const faction_id = holder_faction_id(system)
    if (faction_id === MINMATAR_FACTION_ID) return 'minmatar'
    if (faction_id === AMARR_FACTION_ID) return 'amarr'

    return null
}

const PRIORITY_RANK:Record<string, number> = { high: 0, medium: 1, low: 2 }

export const priority_rank = (priority:string | undefined):number => PRIORITY_RANK[priority ?? 'medium'] ?? 1

/** Operator priority first, then the hottest contest, so the fight that needs people leads the list. */
export const sort_systems_by_contest = (systems:CampaignSystemSummary[]):CampaignSystemSummary[] => {
    return [ ...systems ].sort((a, b) =>
        priority_rank(a.priority) - priority_rank(b.priority)
        || (b.contested_percent ?? 0) - (a.contested_percent ?? 0))
}

export const is_fw_objective_system = (system:CampaignSystemSummary):boolean =>
    system.is_fw_objective !== false

export const fw_objective_systems = (systems:CampaignSystemSummary[]):CampaignSystemSummary[] =>
    systems.filter(is_fw_objective_system)

export const ops_theater_systems = (systems:CampaignSystemSummary[]):CampaignSystemSummary[] =>
    systems.filter(system => !is_fw_objective_system(system))

/** Normalize legacy and current goal wire values. */
export const normalize_campaign_goal = (goal:string):string => {
    switch (goal) {
        case 'capture': return 'take'
        case 'defend': return 'hold'
        case 'contest': return 'pressure'
        case 'scout': return 'recon'
        case 'take':
        case 'hold':
        case 'pressure':
        case 'disrupt':
        case 'recon':
        case 'none':
            return goal
        default:
            return 'none'
    }
}

/** i18n key for a campaign system's goal label. */
export const campaign_goal_i18n_key = (goal:string) => {
    switch (normalize_campaign_goal(goal)) {
        case 'take': return 'campaigns.goal.take' as const
        case 'hold': return 'campaigns.goal.hold' as const
        case 'pressure': return 'campaigns.goal.pressure' as const
        case 'disrupt': return 'campaigns.goal.disrupt' as const
        case 'recon': return 'campaigns.goal.recon' as const
        case 'none': return 'campaigns.goal.none' as const
        default: return 'campaigns.goal.none' as const
    }
}

/** i18n key for the one-line member action behind a goal. */
export const campaign_goal_hint_i18n_key = (goal:string) => {
    switch (normalize_campaign_goal(goal)) {
        case 'take': return 'campaigns.goal.take.hint' as const
        case 'hold': return 'campaigns.goal.hold.hint' as const
        case 'pressure': return 'campaigns.goal.pressure.hint' as const
        case 'disrupt': return 'campaigns.goal.disrupt.hint' as const
        case 'recon': return 'campaigns.goal.recon.hint' as const
        case 'none': return 'campaigns.goal.none.hint' as const
        default: return 'campaigns.goal.none.hint' as const
    }
}

/** Display order for theater goal groups. */
export const CAMPAIGN_GOAL_ORDER = [
    'take',
    'hold',
    'pressure',
    'disrupt',
    'recon',
    'none',
] as const

export const clamp_percent = (value:number | null | undefined):number => {
    if (value === null || value === undefined || Number.isNaN(value)) return 0

    return Math.min(100, Math.max(0, value))
}

/**
 * Offense fills the bar as the system is captured. A hold is the inverse:
 * a stable system is a full bar, and every point the other side puts on it
 * takes some of that bar away.
 */
export const contest_bar_percent = (goal:string, contested:number | null | undefined):number => {
    const captured = clamp_percent(contested)

    return normalize_campaign_goal(goal) === 'hold' ? clamp_percent(100 - captured) : captured
}

/** Turns a 7 day trend into an SVG polyline inside a 100 x 32 viewbox. */
export const trend_sparkline = (trend:CampaignSystemTrendPoint[], width:number = 100, height:number = 32):SparklinePath => {
    const points = trend.filter(point => point.contested_percent !== null)

    if (points.length < 2)
        return { line: '', area: '', empty: true, points: [] }

    const values = points.map(point => point.contested_percent as number)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const span = (max - min) || 1
    const step = width / (points.length - 1)

    const plotted:SparklinePoint[] = values.map((value, index) => ({
        x: index * step,
        y: height - ((value - min) / span) * height,
        captured_at: points[index].captured_at,
        value,
    }))
    const coordinates = plotted.map(point => `${point.x.toFixed(2)},${point.y.toFixed(2)}`)

    return {
        line: coordinates.join(' '),
        area: `0,${height} ${coordinates.join(' ')} ${width},${height}`,
        empty: false,
        points: plotted,
    }
}

export const coverage_bars = (coverage:CampaignCoverageHour[]):CoverageBar[] => {
    const our_max = Math.max(1, ...coverage.map(hour => hour.our_active_days))
    const hostile_max = Math.max(1, ...coverage.map(hour => hour.hostile_activity))

    return coverage.map(hour => ({
        hour: hour.hour,
        our_active_days: hour.our_active_days,
        hostile_activity: hour.hostile_activity,
        our_percent: (hour.our_active_days / our_max) * 100,
        hostile_percent: (hour.hostile_activity / hostile_max) * 100,
    }))
}

export type CampaignStatusChipKey =
    | 'campaigns.chip.gaining'
    | 'campaigns.chip.losing'
    | 'campaigns.chip.holding'

export type CampaignActionErrorKey =
    | 'campaigns.not_enlisted_error'
    | 'campaigns.not_live_error'
    | 'campaigns.action_failed'

export const status_chip_i18n_key = (chip:CampaignStatusChip):CampaignStatusChipKey => {
    switch (chip) {
        case 'gaining': return 'campaigns.chip.gaining'
        case 'losing': return 'campaigns.chip.losing'
        default: return 'campaigns.chip.holding'
    }
}

export const status_chip_color = (chip:CampaignStatusChip):TagColors => {
    switch (chip) {
        case 'gaining': return 'green'
        case 'losing': return 'fleet-red'
        default: return 'fleet-yellow'
    }
}

/**
 * Campaign mutations answer 403 `not_enlisted` and 409 `not scheduled/active`.
 * Both deserve their own message instead of the generic failure.
 */
export const campaign_action_error_key = (error:unknown):CampaignActionErrorKey => {
    const status = (error as { cause?: unknown })?.cause
    const message = String((error as { message?: unknown })?.message ?? '')

    if (status === 403 && message.includes('not_enlisted'))
        return 'campaigns.not_enlisted_error'

    if (status === 409)
        return 'campaigns.not_live_error'

    return 'campaigns.action_failed'
}

/**
 * The detail page and the actions partial both render the stat bar, so the
 * label/value pairing lives here instead of being written out twice.
 */
export const campaign_totals_stats = (
    totals:CampaignTotals,
    t:(key:CampaignTotalsLabelKey) => string,
    format_isk:(value:number) => string,
    kind:string = 'faction_warfare',
):CampaignTotalsStat[] => {
    if (kind === 'strategic') {
        return [
            { label: t('campaigns.stat.enlisted'), value: String(totals.enlisted) },
            { label: t('campaigns.stat.kills'), value: String(totals.kills) },
            { label: t('campaigns.stat.capital_kills'), value: String(totals.capital_kills) },
            { label: t('campaigns.stat.isk_destroyed'), value: format_isk(totals.isk_destroyed) },
            { label: t('campaigns.stat.active_today'), value: String(totals.active_today) },
        ]
    }

    return [
        { label: t('campaigns.stat.enlisted'), value: String(totals.enlisted) },
        { label: t('campaigns.stat.kills'), value: String(totals.kills) },
        { label: t('campaigns.stat.losses'), value: String(totals.losses) },
        { label: t('campaigns.stat.isk_destroyed'), value: format_isk(totals.isk_destroyed) },
        { label: t('campaigns.stat.complexes'), value: String(totals.complexes) },
        { label: t('campaigns.stat.advantage_generated'), value: totals.advantage_generated.toFixed(1) },
        { label: t('campaigns.stat.active_today'), value: String(totals.active_today) },
    ]
}

export type CampaignObjectiveKind =
    | 'offense'
    | 'defense'
    | 'advantage_gain'
    | 'advantage_destroy'
    | 'advantage_maintain'
    | 'structures_reported'
export type CampaignObjectiveStatus = 'winning' | 'losing'

/** One line of the weekly orders table: where, what, how far along, and whether we are winning it. */
export interface CampaignObjectiveRow {
    key:                string;
    kind:               CampaignObjectiveKind;
    label:              string;
    system:             CampaignSystemSummary | null;
    system_name:        string;
    /** Meter fill, 0-100, and where the target sits on it (null = meter fills toward the target). */
    meter_percent:      number;
    marker_percent:     number | null;
    /** Where the bar stood at the start of the change, so the meter can draw the move; null when the wire has no delta. */
    delta_from_percent: number | null;
    /** Progress percent, matching the bar. */
    now_text:           string;
    /** The exact figure behind the bar, for hover: victory points for complexes, the level for advantage. */
    detail_text:        string;
    /** What the change measures: the week so far, or the last day when the week has no opening reading. */
    change_label:       '24h' | 'week';
    /** The bar's move in whole points, signed ("+13%", "-1%", "0%"); empty when there is no reading to compare. */
    change_text:        string;
    /** Which way the bar moved. Every bar reads higher is better, so up is always good news. */
    change_direction:   'up' | 'down' | 'flat';
    /** The last day's move beside a weekly one, for the hover; empty when there is none. */
    change_24h_text:    string;
    /** A complex row whose system changed hands this week: the flip replaces the move, which the reset contest makes meaningless. */
    flipped:            'captured' | 'lost' | null;
    target_text:        string;
    /** The viewer's own contribution this week, for the You tab. */
    yours_text:         string;
    pace:               CampaignPace;
    status:             CampaignObjectiveStatus;
    proposed:           boolean;
}

type ObjectiveT = (key:string) => string

const objective_kind = (metric:string, goal:string):CampaignObjectiveKind => {
    if (metric === 'advantage_gain') return 'advantage_gain'
    if (metric === 'advantage_destroy') return 'advantage_destroy'
    if (metric === 'advantage_maintain') return 'advantage_maintain'
    if (metric === 'structures_reported') return 'structures_reported'
    if (metric === 'days_under_line') return 'defense'
    if (metric === 'victory_points') return 'offense'
    if (goal === 'recon' || goal === 'scout') return 'structures_reported'
    return goal === 'take' || goal === 'pressure' || goal === 'disrupt'
        || goal === 'capture' || goal === 'contest'
        ? 'offense'
        : 'defense'
}

const objective_label = (kind:CampaignObjectiveKind, t:ObjectiveT):string => {
    switch (kind) {
        case 'offense': return t('campaigns.objective.run_complexes')
        case 'defense': return t('campaigns.objective.defend_complexes')
        case 'advantage_gain': return t('campaigns.objective.gain_advantage')
        case 'advantage_destroy': return t('campaigns.objective.destroy_advantage')
        case 'advantage_maintain': return t('campaigns.objective.maintain_advantage')
        case 'structures_reported': return t('campaigns.objective.report_structures')
        default: {
            const _exhaustive: never = kind
            return _exhaustive
        }
    }
}

/** Behind is losing; on pace or ahead is winning. Two words, as the table asks. */
export const objective_status = (pace:CampaignPace):CampaignObjectiveStatus => pace === 'behind' ? 'losing' : 'winning'

export const objective_status_i18n_key = (status:CampaignObjectiveStatus) =>
    status === 'winning' ? 'campaigns.objective.status_winning' as const : 'campaigns.objective.status_losing' as const

const count_text = (count:number, one:string, many:string, t:ObjectiveT):string =>
    t(count === 1 ? one : many).replace('{count}', String(count))

/** A bar's move as the desktop window prints it: whole points, signed, a move under half a point is steady. */
const bar_change = (moved:number) => {
    const rounded = Math.round(moved)

    return {
        change_text: `${rounded > 0 ? '+' : ''}${rounded === 0 ? 0 : rounded}%`,
        change_direction: (rounded > 0 ? 'up' : rounded < 0 ? 'down' : 'flat') as 'up' | 'down' | 'flat',
    }
}

/** 100 and 88 stay whole; 87.6 keeps the tenth. */
const progress_text = (value:number):string => {
    const tenths = Math.round(value * 10) / 10
    const body = Number.isInteger(tenths) ? tenths.toFixed(0) : tenths.toFixed(1)

    return `${body}%`
}

/** "266 of 75,000 victory points", or nothing before the system has a threshold. */
const victory_points_text = (system:CampaignSystemSummary | null, t:ObjectiveT):string => {
    if (!system?.victory_points_threshold) return ''

    return t('campaigns.objective.victory_points_of')
        .replace('{value}', (system.victory_points ?? 0).toLocaleString('en-US'))
        .replace('{threshold}', system.victory_points_threshold.toLocaleString('en-US'))
}

/**
 * The bar is progress in victory points against the flip threshold. Capturing,
 * it fills as ours climb; defending, it is how far the attackers are from
 * flipping it, so a quiet system is full and their victory points drain it.
 *
 * The move is the week's, from the last reading before the week opened, as
 * the row is a weekly objective; the last day's move rides along for the
 * hover. Without a week reading the row falls back to the day. A system that
 * changed hands this week shows the flip instead of a move.
 */
const contest_progress = (
    kind:CampaignObjectiveKind,
    goal:string,
    system:CampaignSystemSummary | null,
    week_progress:CampaignWeekProgress | null,
    t:ObjectiveT,
) => {
    const contested = clamp_percent(system?.contested_percent)
    const contest_goal = kind === 'defense' ? 'hold' : goal
    const meter_percent = contest_bar_percent(contest_goal, contested)
    const from = (change:number | null) => change === null ? null : contest_bar_percent(contest_goal, contested - change)

    const day_change = system?.contested_change_24h ?? null
    const day_from = from(day_change)
    const day_text = day_from === null ? '' : bar_change(meter_percent - day_from).change_text
    const flipped = week_progress?.flipped ?? null
    const week_start = week_progress?.contested_start ?? null
    const weekly = week_progress !== null && (flipped !== null || week_start !== null)
    const delta_from_percent = flipped !== null ? null
        : weekly ? from(contested - (week_start as number))
        : day_from

    return {
        meter_percent,
        delta_from_percent,
        now_text: progress_text(meter_percent),
        detail_text: victory_points_text(system, t),
        change_label: (weekly ? 'week' : '24h') as '24h' | 'week',
        change_24h_text: weekly ? day_text : '',
        flipped,
        ...(delta_from_percent === null
            ? { change_text: '', change_direction: 'flat' as const }
            : bar_change(meter_percent - delta_from_percent)),
    }
}

/**
 * Behind, on pace or ahead when there is no target row to say so: an
 * offensive system is on pace while it gains, a defensive one while it is
 * not losing.
 */
const fallback_pace = (kind:CampaignObjectiveKind, system:CampaignSystemSummary):CampaignPace => {
    if (kind === 'offense') return system.status_chip === 'gaining' ? 'on_pace' : 'behind'
    return system.status_chip === 'losing' ? 'behind' : 'on_pace'
}

/**
 * The rows of the weekly progress table. One per week target, losing rows
 * first. Contest rows show progress, with no target tick: offense fills as
 * the system is captured, defense is the inverse so a stable 0% contested
 * reads 100%. A defensive caption says "stable", or how contested it is.
 * Advantage and structure rows still measure their own level.
 *
 * With no targets yet, one row per system falls back to the system's own
 * goal so the table never asks for nothing.
 */
export const campaign_objective_rows = (
    week:CampaignWeek | null,
    systems:CampaignSystemSummary[],
    t:ObjectiveT,
):CampaignObjectiveRow[] => {
    const by_name = new Map(systems.map(system => [system.name, system]))
    const week_by_name = new Map((week?.progress ?? []).map(row => [row.system, row]))
    const targets = week?.targets ?? []

    if (targets.length === 0) {
        // Fallback rows only for FW objectives; ops theaters wait for
        // structures_reported targets from propose_week.
        return sort_systems_by_contest(fw_objective_systems(systems))
            .map(system => {
                const kind:CampaignObjectiveKind = objective_kind('', system.goal)
                const pace = fallback_pace(kind, system)
                const progress = contest_progress(kind, system.goal, system, week_by_name.get(system.name) ?? null, t)

                return {
                    key: `system-${system.id}`,
                    kind,
                    label: objective_label(kind, t),
                    system,
                    system_name: system.name,
                    meter_percent: progress.meter_percent,
                    marker_percent: null,
                    delta_from_percent: progress.delta_from_percent,
                    now_text: progress.now_text,
                    detail_text: progress.detail_text,
                    change_label: progress.change_label,
                    change_text: progress.change_text,
                    change_direction: progress.change_direction,
                    change_24h_text: progress.change_24h_text,
                    flipped: progress.flipped,
                    target_text: '',
                    yours_text: t('campaigns.objective.yours_none'),
                    pace,
                    status: objective_status(pace),
                    proposed: false,
                }
            })
    }

    // The operator's priority orders the table; within a priority the losing rows come first.
    const rank:Record<CampaignPace, number> = { behind: 0, on_pace: 1, ahead: 2 }
    const system_priority = (name:string) => priority_rank(by_name.get(name)?.priority)

    return [ ...targets ]
        .sort((a, b) => system_priority(a.system) - system_priority(b.system) || rank[a.pace] - rank[b.pace])
        .map(target => {
            const system = by_name.get(target.system) ?? null
            const kind = objective_kind(target.metric, target.goal)
            const goal = target.target || 1

            let meter_percent = 0
            let marker_percent:number | null = null
            let delta_from_percent:number | null = null
            let now_text = ''
            let detail_text = ''
            let change_label:'24h' | 'week' = '24h'
            let change_text = ''
            let change_24h_text = ''
            let flipped:'captured' | 'lost' | null = null
            let direction:'up' | 'down' | 'flat' = 'flat'
            let target_text = ''
            let yours_text = t('campaigns.objective.yours_none')

            if (kind === 'offense' || kind === 'defense') {
                const progress = contest_progress(kind, target.goal || system?.goal || 'take', system, week_by_name.get(target.system) ?? null, t)
                meter_percent = progress.meter_percent
                delta_from_percent = progress.delta_from_percent
                now_text = progress.now_text
                detail_text = progress.detail_text
                change_label = progress.change_label
                change_text = progress.change_text
                change_24h_text = progress.change_24h_text
                flipped = progress.flipped
                direction = progress.change_direction
                if (target.my_complexes > 0)
                    yours_text = count_text(target.my_complexes, 'campaigns.objective.yours_complex', 'campaigns.objective.yours_complexes', t)
            } else if (kind === 'structures_reported') {
                meter_percent = clamp_percent((target.progress / goal) * 100)
                now_text = count_text(
                    Math.round(target.progress),
                    'campaigns.objective.value_structure',
                    'campaigns.objective.value_structures',
                    t,
                )
                change_label = 'week'
                if ((target.my_structures_reported ?? 0) > 0)
                    yours_text = count_text(
                        target.my_structures_reported,
                        'campaigns.objective.yours_structure',
                        'campaigns.objective.yours_structures',
                        t,
                    )
            } else {
                // Levels on the 0-100 advantage scale: ours for gain and
                // maintain, theirs for destroy. Destroy is inverted so the bar
                // fills as their advantage falls, and every bar reads higher
                // is better. The change is the week's move.
                const destroy = kind === 'advantage_destroy'
                const level = destroy
                    ? (system?.advantage_enemy_pct ?? target.progress)
                    : (system?.advantage_our_pct ?? target.progress)
                const bar = (value:number) => clamp_percent(destroy ? 100 - value : value)
                meter_percent = bar(level)
                delta_from_percent = bar(target.baseline)
                now_text = progress_text(meter_percent)
                detail_text = t(destroy ? 'campaigns.objective.level_theirs' : 'campaigns.objective.level_ours').replace('{level}', level.toFixed(0))
                change_label = 'week'
                const moved = bar_change(meter_percent - delta_from_percent)
                change_text = moved.change_text
                direction = moved.change_direction
                if (target.my_advantage_sites > 0)
                    yours_text = count_text(target.my_advantage_sites, 'campaigns.objective.yours_site', 'campaigns.objective.yours_sites', t)
                else if (target.my_readings > 0)
                    yours_text = count_text(target.my_readings, 'campaigns.objective.yours_reading', 'campaigns.objective.yours_readings', t)
            }

            return {
                key: `target-${target.id}`,
                kind,
                label: objective_label(kind, t),
                system,
                system_name: target.system,
                meter_percent,
                marker_percent,
                delta_from_percent,
                now_text,
                detail_text,
                change_label,
                change_text,
                change_direction: direction,
                change_24h_text,
                flipped,
                target_text,
                yours_text,
                pace: target.pace,
                status: objective_status(target.pace),
                proposed: target.proposed,
            }
        })
}

export type CampaignFleetTypeKey =
    | 'campaigns.fleets.type.standing'
    | 'campaigns.fleets.type.gang'
    | 'campaigns.fleets.type.strategic'
    | 'campaigns.fleets.type.non_strategic'
    | 'campaigns.fleets.type.training'
    | 'campaigns.fleets.type.npsi'

export const fleet_type_i18n_key = (type:string):CampaignFleetTypeKey | false => {
    switch (type) {
        case 'standing': return 'campaigns.fleets.type.standing'
        case 'gang': return 'campaigns.fleets.type.gang'
        case 'strategic': return 'campaigns.fleets.type.strategic'
        case 'non_strategic': return 'campaigns.fleets.type.non_strategic'
        case 'training': return 'campaigns.fleets.type.training'
        case 'npsi': return 'campaigns.fleets.type.npsi'
        default: return false
    }
}

/** Rows per page on the Activity tab's tables. */
export const ACTIVITY_PAGE_SIZE = 15

/**
 * Pagination without a count: ask for one row more than the page and, when it
 * arrives, there is a next page. The extra row never renders.
 */
export const paginate = <Row,>(rows:Row[], page_size:number = ACTIVITY_PAGE_SIZE):{ rows:Row[]; has_more:boolean } => ({
    rows: rows.slice(0, page_size),
    has_more: rows.length > page_size,
})
