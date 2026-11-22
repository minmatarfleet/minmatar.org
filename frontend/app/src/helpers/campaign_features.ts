/** Which parts of a campaign page show: the feature switches and the tabs they give. */
import type { CampaignFeatures, CampaignKind, CampaignStructure } from '@dtypes/api.minmatar.org'

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
    | 'discord'
    | 'roles'
    | 'settings'

export interface CampaignTabsOptions {
    kind:           CampaignKind;
    features:       CampaignFeatures;
    /** Systems or areas are attached: a strategic campaign shows Theater only then. */
    has_systems:    boolean;
    can_manage:     boolean;
    /** Before the start nothing is counted yet: no Destruction, Activity, Pilots or You. */
    before_start?:  boolean;
    /** A coordinator from outside the alliance: only the parts shared with them, and their Discord. */
    coordinator_scopes?: string[] | null;
    /** A manager or a holder of a campaign role: the Roles tab. */
    has_roles?:     boolean;
}

/**
 * The tabs a campaign shows, in order. Each switch shows or hides its tab;
 * Activity (the kill feed) gives way to Destruction on a strategic campaign,
 * where the feed is all it holds.
 */
export function campaign_tabs({ kind, features, has_systems, can_manage, before_start = false, coordinator_scopes = null, has_roles = false }: CampaignTabsOptions): CampaignTab[] {
    if (coordinator_scopes) {
        const shared: CampaignTab[] = []
        if (features.structures && coordinator_scopes.includes('structures')) shared.push('structures')
        if (features.timers && coordinator_scopes.includes('timers')) shared.push('timers')
        if (features.fleets && coordinator_scopes.includes('fleets')) shared.push('fleets')
        if (has_roles) shared.push('roles')
        shared.push('discord')
        return shared
    }
    const is_strategic = kind === 'strategic'
    const tabs: CampaignTab[] = []
    if (features.structures) tabs.push('structures')
    if (features.timers) tabs.push('timers')
    if (features.theater && (has_systems || !is_strategic)) tabs.push('systems')
    if (features.fleets) tabs.push('fleets')
    if (!before_start) {
        if (features.destruction) tabs.push('destruction')
        if (!(features.destruction && is_strategic)) tabs.push('activity')
        if (features.pilots) tabs.push('pilots')
    }
    if (features.projects) tabs.push('projects')
    if (!before_start) tabs.push('you')
    if (has_roles || can_manage) tabs.push('roles')
    if (can_manage) tabs.push('settings')
    return tabs
}

/** How many switches are on. */
export function features_on(features: CampaignFeatures): number {
    return CAMPAIGN_FEATURES.filter((feature) => features[feature]).length
}

const STATUS_ORDER: Record<string, number> = { reinforced: 0, anchored: 1, unanchored: 2, destroyed: 3 }

/** Reinforced first by next timer, then anchored, destroyed last (newest kill first). */
export function sort_campaign_structures(structures: CampaignStructure[]): CampaignStructure[] {
    const at = (iso: string | null) => (iso ? new Date(iso).getTime() : Number.POSITIVE_INFINITY)
    return [...structures].sort((a, b) =>
        (STATUS_ORDER[a.status] ?? 2) - (STATUS_ORDER[b.status] ?? 2)
        || (a.status === 'destroyed' ? at(b.destroyed_at) - at(a.destroyed_at) : at(a.timer_at) - at(b.timer_at))
        || a.name.localeCompare(b.name))
}
