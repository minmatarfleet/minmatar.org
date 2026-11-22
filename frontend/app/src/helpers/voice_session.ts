import type { AstroGlobal } from 'astro'
import { get_request_user } from '@helpers/request_user'

export const VOICE_SESSION_COOKIE = 'voice_session'
export const VOICE_SESSION_DAYS = 30

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
