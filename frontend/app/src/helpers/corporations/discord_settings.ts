import type { CorporationDiscordSettings } from '@dtypes/api.minmatar.org'
import type { ui } from '@i18n/ui'

type UiKey = keyof typeof ui['en']

export type DiscordSettingsAction = 'check' | 'save' | 'remove' | 'replace' | 'cancel' | 'disconnect_bot' | 'retry_bot'

const ACTIONS: DiscordSettingsAction[] = ['check', 'save', 'remove', 'replace', 'cancel', 'disconnect_bot', 'retry_bot']

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
