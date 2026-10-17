import type {
    CampaignListItem,
    CampaignSystemSummary,
    CampaignSystemTrendPoint,
    CampaignCoverageHour,
    CampaignPace,
    CampaignStatusChip,
    CampaignTotals,
    CampaignWeek,
    CampaignWeekObjectiveRow,
    CampaignObjectiveCode,
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

/** A week's move on one system: did it help the goal, hurt it, or hold. */
export type CampaignWeekMove = 'ahead' | 'behind' | 'holding' | 'slipping'

/** Smaller than this is noise, same band the status chip uses. */
const WEEK_MOVE_POINT = 0.5
/** A hold is in a good place while contested stays at or under this line. */
const HOLD_LOW_PERCENT = 10
/** A push is holding once contested is this close to the flip threshold. */
const PUSH_THRESHOLD_PERCENT = 80

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

/** The backend's objective codes (campaigns/services/objectives.py) as the table's kinds. */
const OBJECTIVE_KINDS:Record<CampaignObjectiveCode, CampaignObjectiveKind> = {
    capture_complexes: 'offense',
    defend_complexes: 'defense',
    gain_advantage: 'advantage_gain',
    hold_advantage: 'advantage_maintain',
    destroy_advantage: 'advantage_destroy',
    report_structures: 'structures_reported',
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
const victory_points_text = (row:CampaignWeekObjectiveRow, t:ObjectiveT):string => {
    if (!row.victory_points_threshold) return ''

    return t('campaigns.objective.victory_points_of')
        .replace('{value}', (row.victory_points ?? 0).toLocaleString('en-US'))
        .replace('{threshold}', row.victory_points_threshold.toLocaleString('en-US'))
}

/**
 * Behind, on pace or ahead when there is no target row to say so: an
 * offensive system is on pace while it gains, a defensive one while it is
 * not losing.
 */
const fallback_pace = (kind:CampaignObjectiveKind, system:CampaignSystemSummary | null):CampaignPace => {
    if (!system) return 'on_pace'
    if (kind === 'offense') return system.status_chip === 'gaining' ? 'on_pace' : 'behind'
    return system.status_chip === 'losing' ? 'behind' : 'on_pace'
}

/**
 * The rows of the weekly progress table. The backend builds them, in their
 * order, for the website and the desktop window alike
 * (campaigns/services/objectives.py: week.objective_rows); this only words
 * and draws them.
 *
 * Every bar reads higher is better. A complex row's move is the week's, from
 * where it opened, with the last day's for the hover; without a week reading
 * it falls back to the day, and a system that changed hands this week shows
 * the flip instead. Advantage rows move from the target's baseline.
 */
export const campaign_objective_rows = (
    week:CampaignWeek | null,
    systems:CampaignSystemSummary[],
    t:ObjectiveT,
):CampaignObjectiveRow[] => {
    const by_id = new Map(systems.map(system => [system.id, system]))
    const targets = new Map((week?.targets ?? []).map(target => [target.id, target]))

    return (week?.objective_rows ?? []).map(row => {
        const system = by_id.get(row.system_id) ?? null
        const target = row.target_id === null ? null : targets.get(row.target_id) ?? null
        const kind = OBJECTIVE_KINDS[row.objective]
        const meter_percent = row.progress_percent ?? 0
        const has_progress = row.progress_percent !== null

        let delta_from_percent:number | null = null
        let detail_text = ''
        let change_label:'24h' | 'week' = 'week'
        let change_24h_text = ''
        let now_text = has_progress ? progress_text(meter_percent) : ''
        let yours_text = t('campaigns.objective.yours_none')

        if (kind === 'offense' || kind === 'defense') {
            const weekly = row.flipped !== null || row.change_week !== null
            const change = weekly ? row.change_week : row.change_24h
            delta_from_percent = change === null ? null : meter_percent - change
            detail_text = victory_points_text(row, t)
            change_label = weekly ? 'week' : '24h'
            change_24h_text = weekly && row.change_24h !== null ? bar_change(row.change_24h).change_text : ''
            if (target && target.my_complexes > 0)
                yours_text = count_text(target.my_complexes, 'campaigns.objective.yours_complex', 'campaigns.objective.yours_complexes', t)
        } else if (kind === 'structures_reported') {
            now_text = row.structures_reported === null ? '' : count_text(
                Math.round(row.structures_reported),
                'campaigns.objective.value_structure',
                'campaigns.objective.value_structures',
                t,
            )
            if ((target?.my_structures_reported ?? 0) > 0)
                yours_text = count_text(
                    target?.my_structures_reported ?? 0,
                    'campaigns.objective.yours_structure',
                    'campaigns.objective.yours_structures',
                    t,
                )
        } else {
            // Levels on the 0-100 advantage scale: ours for gain and
            // maintain, theirs for destroy (inverted, so the bar fills as
            // theirs falls). The move is the week's.
            delta_from_percent = row.change_week === null ? null : meter_percent - row.change_week
            if (row.advantage_level !== null)
                detail_text = t(kind === 'advantage_destroy' ? 'campaigns.objective.level_theirs' : 'campaigns.objective.level_ours')
                    .replace('{level}', row.advantage_level.toFixed(0))
            if (target && target.my_advantage_sites > 0)
                yours_text = count_text(target.my_advantage_sites, 'campaigns.objective.yours_site', 'campaigns.objective.yours_sites', t)
            else if (target && target.my_readings > 0)
                yours_text = count_text(target.my_readings, 'campaigns.objective.yours_reading', 'campaigns.objective.yours_readings', t)
        }

        const moved = delta_from_percent === null
            ? { change_text: '', change_direction: 'flat' as const }
            : bar_change(meter_percent - delta_from_percent)
        const pace = row.pace ?? fallback_pace(kind, system)

        return {
            key: row.target_id === null ? `system-${row.system_id}` : `target-${row.target_id}`,
            kind,
            label: objective_label(kind, t),
            system,
            system_name: row.name,
            meter_percent,
            marker_percent: null,
            delta_from_percent,
            now_text,
            detail_text,
            change_label,
            change_text: moved.change_text,
            change_direction: moved.change_direction,
            change_24h_text,
            flipped: row.flipped,
            target_text: '',
            yours_text,
            pace,
            status: objective_status(pace),
            proposed: row.proposed,
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
