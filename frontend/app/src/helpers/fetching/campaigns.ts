import type {
    CampaignListItem,
    CampaignSystemSummary,
    CampaignSystemTrendPoint,
    CampaignCoverageHour,
    CampaignPace,
    CampaignStatusChip,
    CampaignTotals,
    CampaignWeekTarget,
} from '@dtypes/api.minmatar.org'
import type { TagColors } from '@dtypes/layout_components'
import { get_campaigns } from '@helpers/api.minmatar.org/campaigns'

export interface CampaignGroups {
    live:       CampaignListItem[];
    upcoming:   CampaignListItem[];
    past:       CampaignListItem[];
}

export interface SparklinePath {
    line:   string;
    area:   string;
    empty:  boolean;
}

export type CampaignTotalsLabelKey =
    | 'campaigns.stat.enlisted'
    | 'campaigns.stat.kills'
    | 'campaigns.stat.losses'
    | 'campaigns.stat.isk_destroyed'
    | 'campaigns.stat.complexes'
    | 'campaigns.stat.advantage_generated'
    | 'campaigns.stat.active_today'

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
export const sort_systems_by_contest = (systems:CampaignSystemSummary[]):CampaignSystemSummary[] => {
    return [ ...systems ].sort((a, b) => (b.contested_percent ?? 0) - (a.contested_percent ?? 0))
}

export const clamp_percent = (value:number | null | undefined):number => {
    if (value === null || value === undefined || Number.isNaN(value)) return 0

    return Math.min(100, Math.max(0, value))
}

/** Turns a 7 day trend into an SVG polyline inside a 100 x 32 viewbox. */
export const trend_sparkline = (trend:CampaignSystemTrendPoint[], width:number = 100, height:number = 32):SparklinePath => {
    const points = trend.filter(point => point.contested_percent !== null)

    if (points.length < 2)
        return { line: '', area: '', empty: true }

    const values = points.map(point => point.contested_percent as number)
    const min = Math.min(...values)
    const max = Math.max(...values)
    const span = (max - min) || 1
    const step = width / (points.length - 1)

    const coordinates = values.map((value, index) => {
        const x = index * step
        const y = height - ((value - min) / span) * height

        return `${x.toFixed(2)},${y.toFixed(2)}`
    })

    return {
        line: coordinates.join(' '),
        area: `0,${height} ${coordinates.join(' ')} ${width},${height}`,
        empty: false,
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
):CampaignTotalsStat[] => {
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
