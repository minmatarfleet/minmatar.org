import type {
    CampaignListItem,
    CampaignSystemSummary,
    CampaignSystemTrendPoint,
    CampaignCoverageHour,
    CampaignPace,
    CampaignStatusChip,
    CampaignTotals,
    CampaignWeekTarget,
    CampaignWeek,
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

export type CampaignPaceKey =
    | 'campaigns.pace.ahead'
    | 'campaigns.pace.behind'
    | 'campaigns.pace.on_pace'

export type CampaignStatusChipKey =
    | 'campaigns.chip.gaining'
    | 'campaigns.chip.losing'
    | 'campaigns.chip.holding'

export type CampaignWeekMetricKey =
    | 'campaigns.week.metric.victory_points'
    | 'campaigns.week.metric.days_under_line'
    | 'campaigns.week.metric.advantage'
    | 'campaigns.week.metric.advantage_gain'
    | 'campaigns.week.metric.advantage_destroy'
    | 'campaigns.week.metric.advantage_maintain'
    | 'campaigns.week.metric.structures_reported'

export type CampaignActionErrorKey =
    | 'campaigns.not_enlisted_error'
    | 'campaigns.not_live_error'
    | 'campaigns.action_failed'

export const pace_i18n_key = (pace:CampaignPace):CampaignPaceKey => {
    switch (pace) {
        case 'ahead': return 'campaigns.pace.ahead'
        case 'behind': return 'campaigns.pace.behind'
        default: return 'campaigns.pace.on_pace'
    }
}

export const pace_color = (pace:CampaignPace):TagColors => {
    switch (pace) {
        case 'ahead': return 'green'
        case 'behind': return 'fleet-red'
        default: return 'fleet-yellow'
    }
}

/** A week's move on one system: did it help the goal, hurt it, or hold. */
export type CampaignWeekMove = 'ahead' | 'behind' | 'holding' | 'slipping'

export type CampaignWeekMoveKey =
    | 'campaigns.week.move.ahead'
    | 'campaigns.week.move.behind'
    | 'campaigns.week.move.holding'
    | 'campaigns.week.move.slipping'

/** Smaller than this is noise, same band the status chip uses. */
const WEEK_MOVE_POINT = 0.5
/** A hold is in a good place while contested stays at or under this line. */
const HOLD_LOW_PERCENT = 10
/** A push is holding once contested is this close to the flip threshold. */
const PUSH_THRESHOLD_PERCENT = 80
/** Below this progress the bar is red; from here to the good line it is yellow. */
const PROGRESS_WARN_PERCENT = 40

const contest_delta = (start:number | null, now:number | null):number | null => {
    if (start === null || now === null) return null

    return now - start
}

/**
 * Good and bad follow the system's goal.
 *
 * Hold: contested falling, or staying at or under the line, helped.
 * Take, pressure, and disrupt: contested rising toward the flip threshold
 * helped. While we are pushing, our advantage rising helped too; a contest
 * move wins when the two disagree.
 */
export const week_contest_move = (
    goal:string,
    contested_start:number | null,
    contested_now:number | null,
    advantage_our_start:number | null = null,
    advantage_our_now:number | null = null,
):CampaignWeekMove => {
    const normalized = normalize_campaign_goal(goal)
    const pushing = normalized === 'take' || normalized === 'pressure' || normalized === 'disrupt'
    const contest = contest_delta(contested_start, contested_now)
    const contest_up = contest !== null && contest > WEEK_MOVE_POINT
    const contest_down = contest !== null && contest < -WEEK_MOVE_POINT
    const advantage = pushing ? contest_delta(advantage_our_start, advantage_our_now) : null
    const advantage_up = advantage !== null && advantage > WEEK_MOVE_POINT
    const advantage_down = advantage !== null && advantage < -WEEK_MOVE_POINT

    if (normalized === 'hold') {
        if (contest_down) return 'ahead'
        if (contest_up) return 'slipping'
        if (contested_now === null) return 'holding'

        return contested_now <= HOLD_LOW_PERCENT ? 'holding' : 'behind'
    }

    if (pushing) {
        if (contest_up) return 'ahead'
        if (contest_down) return 'slipping'
        if (advantage_up) return 'ahead'
        if (advantage_down) return 'slipping'
        if (contested_now === null) return 'holding'

        return contested_now >= PUSH_THRESHOLD_PERCENT ? 'holding' : 'behind'
    }

    return 'holding'
}

export const week_move_i18n_key = (move:CampaignWeekMove):CampaignWeekMoveKey => {
    switch (move) {
        case 'ahead': return 'campaigns.week.move.ahead'
        case 'behind': return 'campaigns.week.move.behind'
        case 'holding': return 'campaigns.week.move.holding'
        case 'slipping': return 'campaigns.week.move.slipping'
        default: {
            const _exhaustive: never = move
            return _exhaustive
        }
    }
}

export const week_move_color = (move:CampaignWeekMove):TagColors => {
    switch (move) {
        case 'ahead': return 'green'
        case 'behind': return 'fleet-red'
        case 'holding': return 'fleet-yellow'
        case 'slipping': return 'fleet-red'
        default: {
            const _exhaustive: never = move
            return _exhaustive
        }
    }
}

/** Where the meter ticks the line that matters for this goal. */
export const week_contest_marker = (goal:string):number | null => {
    const normalized = normalize_campaign_goal(goal)

    if (normalized === 'hold') return HOLD_LOW_PERCENT
    if (normalized === 'take' || normalized === 'pressure' || normalized === 'disrupt')
        return PUSH_THRESHOLD_PERCENT

    return null
}

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

/** Progress and the "where we should be by now" marker, both as percentages. */
export const week_target_progress = (target:CampaignWeekTarget) => {
    const goal = target.target || 1

    return {
        progress_percent: clamp_percent((target.progress / goal) * 100),
        pace_percent: clamp_percent((target.pace_expected / goal) * 100),
    }
}

/** Week targets carry a backend slug; map it to a label the UI can translate. */
export const week_metric_i18n_key = (metric:string):CampaignWeekMetricKey | false => {
    switch (metric) {
        case 'victory_points': return 'campaigns.week.metric.victory_points'
        case 'days_under_line': return 'campaigns.week.metric.days_under_line'
        case 'advantage': return 'campaigns.week.metric.advantage'
        case 'advantage_gain': return 'campaigns.week.metric.advantage_gain'
        case 'advantage_destroy': return 'campaigns.week.metric.advantage_destroy'
        case 'advantage_maintain': return 'campaigns.week.metric.advantage_maintain'
        case 'structures_reported': return 'campaigns.week.metric.structures_reported'
        default: return false
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
    /** Where the bar stood 24h ago, so the meter can hatch the change; null when the wire has no delta. */
    delta_from_percent: number | null;
    /** Progress percent, matching the bar. */
    now_text:           string;
    /** Why the bar is where it is. Defensive rows say "stable" or the contested percent. */
    detail_text:        string;
    /** What the middle label measures: the last day for contest metrics, the week so far for advantage levels. */
    change_label:       '24h' | 'week';
    change_text:        string;
    change_direction:   'up' | 'down' | 'flat';
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

export const objective_status_color = (status:CampaignObjectiveStatus):TagColors => status === 'winning' ? 'green' : 'fleet-red'

/**
 * Contest bars follow progress, where higher is better. A hold is already
 * inverted, so a stable system is green and enemy victory points walk it
 * through yellow to red. A push is green once it is close to flipping.
 */
export const progress_bar_color = (kind:'offense' | 'defense', percent:number):TagColors => {
    const good = kind === 'defense' ? 100 - HOLD_LOW_PERCENT : PUSH_THRESHOLD_PERCENT

    if (percent >= good) return 'green'
    if (percent >= PROGRESS_WARN_PERCENT) return 'fleet-yellow'

    return 'fleet-red'
}

const count_text = (count:number, one:string, many:string, t:ObjectiveT):string =>
    t(count === 1 ? one : many).replace('{count}', String(count))

const change_direction = (change:number):'up' | 'down' | 'flat' => change > 0 ? 'up' : change < 0 ? 'down' : 'flat'

/** 100 and 88 stay whole; 87.6 keeps the tenth. */
const progress_text = (value:number):string => {
    const tenths = Math.round(value * 10) / 10
    const body = Number.isInteger(tenths) ? tenths.toFixed(0) : tenths.toFixed(1)

    return `${body}%`
}

/**
 * The bar is progress. A hold at 0% contested is 100% done, and the caption
 * says why: stable, or how contested it has become.
 */
const contest_progress = (
    kind:CampaignObjectiveKind,
    goal:string,
    contested:number,
    change:number,
    t:ObjectiveT,
) => {
    const contest_goal = kind === 'defense' ? 'hold' : goal
    const meter_percent = contest_bar_percent(contest_goal, contested)
    const delta_from_percent = contest_bar_percent(contest_goal, contested - change)
    const moved = meter_percent - delta_from_percent
    const detail_text = kind !== 'defense' ? ''
        : contested < 0.05
            ? t('campaigns.objective.stable')
            : t('campaigns.objective.contested_now').replace('{contested}', contested.toFixed(1))

    return {
        meter_percent,
        delta_from_percent,
        now_text: progress_text(meter_percent),
        detail_text,
        change_text: Math.abs(moved) < 0.05 ? '' : `${Math.abs(moved).toFixed(1)}%`,
        change_direction: change_direction(moved),
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
    const targets = week?.targets ?? []

    if (targets.length === 0) {
        // Fallback rows only for FW objectives; ops theaters wait for
        // structures_reported targets from propose_week.
        return sort_systems_by_contest(fw_objective_systems(systems))
            .map(system => {
                const kind:CampaignObjectiveKind = objective_kind('', system.goal)
                const contested = clamp_percent(system.contested_percent)
                const change = system.contested_change_24h ?? 0
                const pace = fallback_pace(kind, system)
                const progress = contest_progress(kind, system.goal, contested, change, t)

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
                    change_label: '24h' as const,
                    change_text: progress.change_text,
                    change_direction: progress.change_direction,
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
            const change = system?.contested_change_24h ?? 0
            const goal = target.target || 1

            let meter_percent = 0
            let marker_percent:number | null = null
            let delta_from_percent:number | null = null
            let now_text = ''
            let detail_text = ''
            let change_label:'24h' | 'week' = '24h'
            let change_text = ''
            let direction:'up' | 'down' | 'flat' = 'flat'
            let target_text = ''
            let yours_text = t('campaigns.objective.yours_none')

            if (kind === 'offense' || kind === 'defense') {
                const contested = clamp_percent(system?.contested_percent)
                const progress = contest_progress(kind, target.goal || system?.goal || 'take', contested, change, t)
                meter_percent = progress.meter_percent
                delta_from_percent = progress.delta_from_percent
                now_text = progress.now_text
                detail_text = progress.detail_text
                change_text = progress.change_text
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
                // maintain, theirs for destroy. The bar is the level itself,
                // and the hatch is the week's move.
                const destroy = kind === 'advantage_destroy'
                const level = destroy
                    ? (system?.advantage_enemy_pct ?? target.progress)
                    : (system?.advantage_our_pct ?? target.progress)
                const moved = level - target.baseline
                meter_percent = clamp_percent(level)
                delta_from_percent = clamp_percent(target.baseline)
                now_text = t(destroy ? 'campaigns.objective.level_theirs' : 'campaigns.objective.level_ours').replace('{level}', level.toFixed(0))
                change_label = 'week'
                change_text = Math.abs(moved) < 0.5 ? '' : `${Math.abs(moved).toFixed(0)}%`
                direction = change_direction(moved)
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
