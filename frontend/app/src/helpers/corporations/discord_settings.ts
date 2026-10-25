import type { CorporationDiscordSettings } from '@dtypes/api.minmatar.org'
import type { ui } from '@i18n/ui'

type UiKey = keyof typeof ui['en']

export type DiscordSettingsAction = 'check' | 'save' | 'remove' | 'replace' | 'cancel'

const ACTIONS: DiscordSettingsAction[] = ['check', 'save', 'remove', 'replace', 'cancel']

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
    settings: Pick<CorporationDiscordSettings, 'exists' | 'status'>,
    labels: { not_set: string, set: string, dead: string },
): string {
    if (!settings.exists)
        return labels.not_set
    return settings.status === 'dead' ? labels.dead : labels.set
}
