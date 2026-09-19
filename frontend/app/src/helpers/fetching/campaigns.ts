import type {
    CampaignListItem,
    CampaignSystemSummary,
    CampaignSystemTrendPoint,
    CampaignCoverageHour,
    CampaignPace,
    CampaignStatusChip,
    CampaignWeekTarget,
} from '@dtypes/api.minmatar.org'
import type { TagColors } from '@dtypes/layout_components'

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

export interface CoverageBar {
    hour:               number;
    our_active_days:    number;
    hostile_activity:   number;
    our_percent:        number;
    hostile_percent:    number;
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

export const pace_i18n_key = (pace:CampaignPace):string => {
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

export const status_chip_i18n_key = (chip:CampaignStatusChip):string => {
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
