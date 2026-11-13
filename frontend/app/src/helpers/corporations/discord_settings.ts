import type { CorporationDiscordSettings } from '@dtypes/api.minmatar.org'
import type { ui } from '@i18n/ui'

export type UiKey = keyof typeof ui['en']

export type DiscordSettingsAction = 'check' | 'save' | 'remove' | 'replace' | 'cancel' | 'disconnect_bot' | 'retry_bot' | 'save_roles' | 'refresh_roles' | 'save_members' | 'save_access' | 'approve_members'

const ACTIONS: DiscordSettingsAction[] = ['check', 'save', 'remove', 'replace', 'cancel', 'disconnect_bot', 'retry_bot', 'save_roles', 'refresh_roles', 'save_members', 'save_access', 'approve_members']

// Roles a corporation server can hand out, in the order Settings lists them.
export const DISCORD_CORPORATION_ROLE_STATES = [
    'member',
    'director',
    'recruiter',
    'structure_manager',
    'alliance_member',
] as const

export type DiscordCorporationRoleState = typeof DISCORD_CORPORATION_ROLE_STATES[number]

/**
 * The role rows Settings renders. Member always shows; the rest sit behind
 * "Add a role" until added, except those already mapped.
 */
export function discord_access_roles(mappings: { state: string, role_id?: string | null }[]) {
    const mapped = new Set(mappings.filter((mapping) => mapping.role_id).map((mapping) => mapping.state))
    const extra = DISCORD_CORPORATION_ROLE_STATES.filter((state) => state !== 'member')
    return {
        all: [...DISCORD_CORPORATION_ROLE_STATES],
        extra,
        added: extra.filter((state) => mapped.has(state)),
    }
}

/**
 * The cleanup option Settings starts on. A server without a policy starts
 * on Notify the CEO, the default; one saved before actions existed (no
 * `action` field) removes, as it did then.
 */
export function discord_initial_action(policy: string | null | undefined, action: string | null | undefined): string {
    if (!policy)
        return 'notify'
    if (action === undefined)
        return 'remove'
    return action ?? ''
}

/** The cleanup choice as posted: notify, remove, or null (remove roles only). */
export function parse_member_action(value: unknown): 'notify' | 'remove' | null {
    return value === 'notify' || value === 'remove' ? value : null
}

// The pending list's Keep buttons post `keep:<discord id>`.
const KEEP_PREFIX = 'keep:'

/** The Discord id a Keep button posted, or null. */
export function parse_keep_member(value: unknown): string | null {
    if (typeof value !== 'string' || !value.startsWith(KEEP_PREFIX))
        return null
    const id = value.slice(KEEP_PREFIX.length)
    return /^\d{1,20}$/.test(id) ? id : null
}

export function keep_member_action(discord_id: string): string {
    return `${KEEP_PREFIX}${discord_id}`
}

/** Exemptions as typed in the textarea: one per line, commas allowed. */
export function parse_exemptions(value: unknown): string[] {
    return String(value ?? '')
        .split(/[\n,]/)
        .map((line) => line.trim())
        .filter(Boolean)
}

/** Hours and minutes until `when`, or null once it's due. */
export function discord_removal_eta(when: string, now = Date.now()): string | null {
    const minutes = Math.ceil((new Date(when).getTime() - now) / 60_000)
    if (!Number.isFinite(minutes) || minutes <= 0)
        return null
    const hours = Math.floor(minutes / 60)
    if (hours >= 48)
        return `${Math.round(hours / 24)}d`
    return hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`
}

export interface DiscordSettingsFlash {
    kind: 'success' | 'error';
    key: UiKey;
}

export function parse_discord_action(value: unknown): DiscordSettingsAction {
    return ACTIONS.find((action) => action === value) ?? 'check'
}

// Codes from the backend's eveonline.helpers.corporations.discord_invite.
const SAVE_ERRORS: Record<string, UiKey> = {
    url_required: 'corporations.discord.error_url_required',
    not_discord_invite: 'corporations.discord.error_not_discord_invite',
    invite_not_found: 'corporations.discord.error_invite_not_found',
    invite_expires: 'corporations.discord.error_invite_expires',
    not_a_server: 'corporations.discord.error_not_a_server',
    duplicate_role: 'corporations.discord.error_duplicate',
    unknown_role: 'corporations.discord.error_unknown',
    not_connected: 'corporations.discord.error_not_connected',
    cannot_manage_roles: 'corporations.discord.error_cannot_manage',
    invalid_username: 'corporations.discord.error_invalid_username',
    too_many_exemptions: 'corporations.discord.error_too_many_exemptions',
    cannot_kick_members: 'corporations.discord.error_cannot_kick_members',
    not_pending: 'corporations.discord.error_not_pending',
    not_held: 'corporations.discord.error_not_held',
    state_not_allowed: 'corporations.discord.error_unknown',
}

export function discord_error_key(code: string): UiKey {
    return SAVE_ERRORS[code] ?? 'corporations.settings.error_save'
}

const STATUS_KEYS: Record<string, UiKey> = {
    ok: 'corporations.discord.status_ok',
    dead: 'corporations.discord.status_dead',
    unchecked: 'corporations.discord.status_unchecked',
}

export function discord_status_key(status: string | null): UiKey {
    return STATUS_KEYS[status ?? ''] ?? 'corporations.discord.status_unchecked'
}

/** The invite without its scheme, as people type it: discord.gg/yourcorp. */
export function discord_invite_label(url: string | null): string {
    return (url ?? '').replace(/^https?:\/\//, '')
}

/** Initials for a server without an icon. */
export function discord_server_initials(name: string | null): string {
    const words = (name ?? '').trim().split(/\s+/).filter(Boolean)
    return words.slice(0, 2).map((word) => [...word][0]).join('').toUpperCase() || '#'
}

/** One line for the collapsed Discord section header. */
export function discord_section_summary(
    settings: Pick<CorporationDiscordSettings, 'exists' | 'status'> & {
        bot?: Pick<CorporationDiscordSettings['bot'], 'connected' | 'status'>
    },
    labels: { not_set: string, set: string, dead: string, setting_up?: string, attention?: string },
): string {
    if (settings.bot?.connected) {
        if (settings.bot.status === 'pending')
            return labels.setting_up ?? labels.set
        if (discord_bot_needs_attention(settings.bot.status))
            return labels.attention ?? labels.dead
        return labels.set
    }
    if (!settings.exists)
        return labels.not_set
    return settings.status === 'dead' ? labels.dead : labels.set
}

/** The bot is linked but makes no invites: Settings asks the CEO to fix it. */
export function discord_bot_needs_attention(status: string | null | undefined): boolean {
    return status === 'no_permission' || status === 'removed'
}

const BOT_STATUS_KEYS: Record<string, UiKey> = {
    pending: 'corporations.discord.bot_status_pending',
    ok: 'corporations.discord.status_ok',
    no_permission: 'corporations.discord.bot_status_no_permission',
    removed: 'corporations.discord.bot_status_removed',
}

export function discord_bot_status_key(status: string | null): UiKey {
    return BOT_STATUS_KEYS[status ?? ''] ?? 'corporations.discord.bot_status_pending'
}

// Codes from the bot install callback (get_corporation_discord_bot_callback).
const BOT_CONNECT_ERRORS: Record<string, UiKey> = {
    denied: 'corporations.discord.bot_error_denied',
    alliance_server: 'corporations.discord.bot_error_alliance_server',
    guild_taken: 'corporations.discord.bot_error_guild_taken',
    missing_guild: 'corporations.discord.bot_error_missing_guild',
    not_allowed: 'corporations.discord.bot_error_not_allowed',
    session_expired: 'corporations.discord.bot_error_session_expired',
}

/** The flash for a return from Discord's bot install page, if any. */
export function discord_bot_connect_flash(params: URLSearchParams): DiscordSettingsFlash | null {
    if (params.get('discord_bot') === 'connected')
        return { kind: 'success', key: 'corporations.discord.bot_connected' }
    const error = params.get('discord_bot_error')
    if (!error)
        return null
    return { kind: 'error', key: BOT_CONNECT_ERRORS[error] ?? 'corporations.discord.bot_error' }
}

// Settings re-asks every few seconds while the bot sets up, then gives up.
export const DISCORD_BOT_POLL_LIMIT = 20

/** The next poll number while the bot is setting up, or null to stop. */
export function discord_bot_next_poll(status: string | null, poll: number): number | null {
    if (status !== 'pending' || poll >= DISCORD_BOT_POLL_LIMIT)
        return null
    return poll + 1
}

/** True until a re-fetch writes a role catalog newer than `since`. */
export function discord_roles_refresh_pending(
    checked_at: string | null | undefined,
    since: string | null | undefined,
): boolean {
    if (!since)
        return false
    const since_ms = Date.parse(since)
    if (Number.isNaN(since_ms))
        return false
    if (!checked_at)
        return true
    const checked_ms = Date.parse(checked_at)
    if (Number.isNaN(checked_ms))
        return true
    return checked_ms <= since_ms
}

/** The next poll number while a role re-fetch is in flight, or null to stop. */
export function discord_roles_next_poll(pending: boolean, poll: number): number | null {
    if (!pending || poll >= DISCORD_BOT_POLL_LIMIT)
        return null
    return poll + 1
}
