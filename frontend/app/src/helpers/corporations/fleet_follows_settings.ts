/**
 * Fleet pings: a corporation follows a tribe group's fleet posts in its own
 * Discord (docs/tribes/group-fleet-roundup.md). Pure helpers for the
 * corporation's Settings section and the group's approval list.
 */
import type { ui } from '@i18n/ui'

type UiKey = keyof typeof ui['en']

export type FleetFollowAction = 'save' | 'remove'
export type GroupFollowDecision = 'approve' | 'revoke'

export function parse_fleet_follow_action(value: unknown): FleetFollowAction {
    return value === 'remove' ? 'remove' : 'save'
}

export function group_follow_decision(value: unknown): GroupFollowDecision | null {
    return value === 'approve' || value === 'revoke' ? value : null
}

// Codes from the backend's eveonline.helpers.corporations.fleet_follows.
const ERRORS: Record<string, UiKey> = {
    not_eligible: 'corporations.fleet_pings.error_not_eligible',
    not_connected: 'corporations.fleet_pings.error_not_connected',
    unknown_channel: 'corporations.fleet_pings.error_unknown_channel',
    discord_unreachable: 'corporations.fleet_pings.error_discord_unreachable',
    unknown_group: 'corporations.fleet_pings.error_unknown_group',
}

export function fleet_follow_error_key(code: string): UiKey {
    return ERRORS[code] ?? 'corporations.settings.error_save'
}

const STATUSES: Record<string, UiKey> = {
    requested: 'corporations.fleet_pings.status_requested',
    approved: 'corporations.fleet_pings.status_approved',
    revoked: 'corporations.fleet_pings.status_revoked',
}

export function fleet_follow_status_key(status: string): UiKey {
    return STATUSES[status] ?? 'corporations.fleet_pings.status_requested'
}

const WARNINGS: Record<string, UiKey> = {
    cant_post: 'corporations.fleet_pings.warning_cant_post',
    no_embeds: 'corporations.fleet_pings.warning_no_embeds',
    no_here: 'corporations.fleet_pings.warning_no_here',
}

export function fleet_follow_warning_key(warning: string): UiKey {
    return WARNINGS[warning] ?? 'corporations.fleet_pings.warning_cant_post'
}
