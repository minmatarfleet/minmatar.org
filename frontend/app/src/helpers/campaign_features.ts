/** Which parts of a campaign page show: the feature switches and the tabs they give. */
import type { CampaignFeatures, CampaignKind } from '@dtypes/api.minmatar.org'

/** In the order the Settings tab lists them (backend `CAMPAIGN_FEATURES`). */
export const CAMPAIGN_FEATURES = [
    'weekly_progress',
    'structures',
    'timers',
    'theater',
    'fleets',
    'destruction',
    'pilots',
    'projects',
] as const

export type CampaignFeature = typeof CAMPAIGN_FEATURES[number]

export type CampaignTab =
    | 'structures'
    | 'timers'
    | 'systems'
    | 'fleets'
    | 'destruction'
    | 'activity'
    | 'pilots'
    | 'projects'
    | 'you'
    | 'settings'

export interface CampaignTabsOptions {
    kind:           CampaignKind;
    features:       CampaignFeatures;
    /** Systems or areas are attached: a strategic campaign shows Theater only then. */
    has_systems:    boolean;
    can_manage:     boolean;
}

/**
 * The tabs a campaign shows, in order. Each switch shows or hides its tab;
 * Activity (the kill feed) gives way to Destruction on a strategic campaign,
 * where the feed is all it holds.
 */
export function campaign_tabs({ kind, features, has_systems, can_manage }: CampaignTabsOptions): CampaignTab[] {
    const is_strategic = kind === 'strategic'
    const tabs: CampaignTab[] = []
    if (features.structures) tabs.push('structures')
    if (features.timers) tabs.push('timers')
    if (features.theater && (has_systems || !is_strategic)) tabs.push('systems')
    if (features.fleets) tabs.push('fleets')
    if (features.destruction) tabs.push('destruction')
    if (!(features.destruction && is_strategic)) tabs.push('activity')
    if (features.pilots) tabs.push('pilots')
    if (features.projects) tabs.push('projects')
    tabs.push('you')
    if (can_manage) tabs.push('settings')
    return tabs
}

/** How many switches are on. */
export function features_on(features: CampaignFeatures): number {
    return CAMPAIGN_FEATURES.filter((feature) => features[feature]).length
}
