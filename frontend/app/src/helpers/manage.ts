import manage_screens from '@json/manage_screens.json'
import type { ManageQueue, ManageSummary } from '@dtypes/api.minmatar.org'
import { can, feature_allows, legacy_superuser, type GateContext, type GateKey } from '@helpers/gates'

/**
 * The Manage hub registry (src/json/manage_screens.json): every settings
 * screen with its group, route and the gate its page opens with, plus the
 * queues the hub counts. The backend decides access from its copy
 * (backend/manage_hub/screens.py); its tests fail when the two drift.
 */

export type ManageGroupKey = 'fleets' | 'market' | 'content' | 'learning' | 'ships' | 'people'
export type ManageScreenKey =
    | 'campaigns' | 'payout_codes' | 'npsi_feeds' | 'structure_timers'
    | 'market_hubs' | 'buyback' | 'freight_routes' | 'lp_desk'
    | 'help_tickets' | 'post_tags' | 'reddit' | 'creators'
    | 'guides' | 'certificates' | 'onboarding' | 'skillsets'
    | 'doctrines' | 'srp_amounts'
    | 'alliance_health' | 'surveys'
export type ManageQueueKey = 'doctrine_changes' | 'reddit_posts' | 'payout_codes' | 'npsi_feeds'

export interface ManageScreenDefinition {
    key:    ManageScreenKey;
    group:  ManageGroupKey;
    path:   string;
    /** The site gate the page opens with. */
    gate?:  GateKey;
    /** Or the backend check the page asks the API for. */
    check?: 'lp_desk' | 'alliance_health';
}

export interface ManageQueueDefinition {
    key:    ManageQueueKey;
    screen: ManageScreenKey;
    tone?:  'warn';
}

export const MANAGE_GROUPS = manage_screens.groups as ManageGroupKey[]
export const MANAGE_SCREENS = manage_screens.screens as ManageScreenDefinition[]
export const MANAGE_QUEUES = manage_screens.queues as ManageQueueDefinition[]

export function manage_screen(key: string): ManageScreenDefinition | undefined {
    return MANAGE_SCREENS.find((screen) => screen.key === key)
}

/**
 * The features the API checks behind the two pages without a site gate
 * (industry/endpoints/loyalty/auth_helpers.py, alliance/helpers/access.py).
 * Officers reach alliance health for their own corporation too; the hub
 * page lists them from the API, the Neocom check only sees the feature.
 */
const CHECK_FEATURES: Record<NonNullable<ManageScreenDefinition['check']>, string> = {
    lp_desk: 'industry.loyalty.manage',
    alliance_health: 'alliance.health',
}

/**
 * The `manage.hub` gate: the user can reach at least one manage screen.
 * Decided from the gates the page already loaded, so the Neocom can ask on
 * every page without an API call. The hub page itself lists screens from
 * GET /api/manage/summary, which also runs the API-side checks.
 */
export function can_manage_hub(gates: GateContext): boolean {
    if (!gates.user_id) return false

    return MANAGE_SCREENS.some((screen) => {
        if (screen.check)
            return gates.features.includes(CHECK_FEATURES[screen.check])
        // Custom gate (helpers/doctrine_editor.ts): superuser or the feature.
        if (screen.gate === 'fittings.doctrine.edit')
            return (gates.gate_source !== 'features' && legacy_superuser(gates))
                || feature_allows(gates, screen.gate)
        return screen.gate ? can(gates, screen.gate) : false
    })
}

/** The id of a SettingsSection's summary span, for SectionSummary's hx-swap-oob. */
export function section_summary_id(section_id: string): string {
    return `${section_id}-summary`
}

/** Queues with something waiting, in registry order. */
export function waiting_queues(summary: ManageSummary | null): ManageQueue[] {
    return (summary?.queues ?? []).filter((queue) => queue.count > 0)
}

/** "3 h", "1 d": how long ago, in the largest whole unit (minutes up to an hour). */
export function age_parts(iso: string | null | undefined, now: Date = new Date()): { value: number, unit: 'minutes' | 'hours' | 'days' } | null {
    if (!iso) return null
    const ms = now.getTime() - new Date(iso).getTime()
    if (Number.isNaN(ms)) return null
    const minutes = Math.max(0, Math.floor(ms / 60_000))
    if (minutes < 60) return { value: Math.max(1, minutes), unit: 'minutes' }
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return { value: hours, unit: 'hours' }
    return { value: Math.floor(hours / 24), unit: 'days' }
}

/** EVE time (UTC) "HH:MM", or "31 Oct" when not today. */
export function eve_short_time(iso: string | null | undefined, lang: string, now: Date = new Date()): string {
    if (!iso) return ''
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) return ''
    const same_day = date.toISOString().slice(0, 10) === now.toISOString().slice(0, 10)
    return same_day
        ? date.toISOString().slice(11, 16)
        : date.toLocaleDateString(lang, { day: 'numeric', month: 'short', timeZone: 'UTC' })
}
