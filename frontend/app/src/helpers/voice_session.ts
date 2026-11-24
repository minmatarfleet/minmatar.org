import type { AstroGlobal } from 'astro'
import { get_request_user } from '@helpers/request_user'

export const VOICE_SESSION_COOKIE = 'voice_session'
export const VOICE_SESSION_DAYS = 30
export const VOICE_LOGIN_STATE_COOKIE = 'voice_login_state'
export const VOICE_LOGIN_STATE_MINUTES = 10

/** A random state for one EVE sign-in (base64url, 32 bytes). */
export function new_login_state(): string {
    const bytes = crypto.getRandomValues(new Uint8Array(32))
    return btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** True when the state EVE sign-in returned is the one this browser started with. */
export function login_state_matches(returned:string | null | undefined, expected:string | null | undefined): boolean {
    return !!returned && !!expected && returned.length >= 16 && returned === expected
}

export interface VoiceSession {
    token:  string;
    kind:   'guest' | 'member';
}

/**
 * Who /voice acts for: a site member's own session first, else the
 * EVE-only voice session set by /voice/login.
 */
export function get_voice_session(astro:AstroGlobal | any): VoiceSession | null {
    const { auth_token, user } = get_request_user(astro)
    if (user && auth_token)
        return { token: auth_token, kind: 'member' }
    const voice_token = astro.cookies.get(VOICE_SESSION_COOKIE)?.value
    if (voice_token)
        return { token: voice_token, kind: 'guest' }
    return null
}

/** A positive integer id (character, fleet, certificate) from a query or form value, else null. */
export function parse_positive_id(value:unknown): number | null {
    const parsed = Number.parseInt(String(value ?? ''), 10)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

export const parse_character_id = parse_positive_id

/** The FC's "1234 = Auxiliary A" lines as the wing map the API takes. */
export function parse_wings(text:string): Record<string, string> {
    const wings: Record<string, string> = {}
    for (const line of text.split('\n')) {
        const [wing, channel] = line.split('=').map((part) => part.trim())
        if (wing && channel) wings[wing] = channel
    }
    return wings
}

/** Set once this browser has connected (no token in it): /voice then offers
 * "Sign in and connect" instead of the first-time setup. */
export const VOICE_RETURNING_COOKIE = 'voice_returning'
export const VOICE_RETURNING_DAYS = 365
/** What /voice/login does after the EVE sign-in ("connect": open Mumble straight away). */
export const VOICE_LOGIN_THEN_COOKIE = 'voice_login_then'
/** How long after Connect the page watches for the pilot to reach the server. */
export const CONNECT_WATCH_SECONDS = 150

export type VoiceDevice = 'windows' | 'macos' | 'linux' | 'android' | 'ios'
export const VOICE_DEVICES: VoiceDevice[] = ['windows', 'macos', 'linux', 'android', 'ios']

/** The device a browser's user agent most likely runs on; Windows when unsure. */
export function detect_device(user_agent:string | null | undefined): VoiceDevice {
    const ua = (user_agent ?? '').toLowerCase()
    if (/iphone|ipad|ipod/.test(ua)) return 'ios'
    if (ua.includes('android')) return 'android'
    if (/macintosh|mac os x/.test(ua)) return 'macos'
    if (/linux|x11|cros/.test(ua)) return 'linux'
    return 'windows'
}

/** Which screen /voice shows for a status. */
export type VoiceStep = 'banned' | 'not_main' | 'waiting' | 'setup' | 'ready'

export function voice_step(status:{ banned: boolean, admitted: boolean, reason: string, certificate_count: number }): VoiceStep {
    if (status.banned) return 'banned'
    if (!status.admitted) return status.reason === 'not_main' ? 'not_main' : 'waiting'
    return status.certificate_count > 0 ? 'ready' : 'setup'
}

/** A screen asked for by the page's own links: `?view=`. */
export type VoiceView = 'setup' | 'keys' | 'trouble'

export function parse_voice_view(value:unknown): VoiceView | null {
    return value === 'setup' || value === 'keys' || value === 'trouble' ? value : null
}

/** The `since` a Connect started watching from, while the watch lasts; else null. */
export function parse_since(value:unknown, now:Date = new Date()): Date | null {
    const since = new Date(String(value ?? ''))
    if (Number.isNaN(since.getTime())) return null
    const age = (now.getTime() - since.getTime()) / 1000
    return age >= -60 && age <= CONNECT_WATCH_SECONDS ? since : null
}

/** True when a certificate was bound or used at or after `since`: the pilot reached the server.
 * Ten seconds of slack covers the clock difference between the website and the API. */
export function connected_since(certificates:{ created_at: string, last_used_at: string | null }[], since:Date): boolean {
    const from = since.getTime() - 10_000
    return certificates.some((certificate) =>
        [certificate.created_at, certificate.last_used_at].some((at) => !!at && new Date(at).getTime() >= from))
}
