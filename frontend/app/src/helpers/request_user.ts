import * as jose from 'jose'

import type { User } from '@dtypes/jwt'

/**
 * The signed-in user for this request, read from the `auth_token` cookie.
 *
 * The site only decodes the JWT; the backend verifies it on every API call.
 * Pages, partials, components and API routes all call this instead of reading
 * the cookie themselves, and get_gates() builds the gate context from it.
 */
export interface RequestUser {
    /** The raw session token to pass to the backend, or false when signed out. */
    auth_token: string | false;
    /** The decoded token, or false when signed out or the cookie is unreadable. */
    user:       User | false;
}

interface AstroLike {
    cookies: { has(name: string): boolean; get(name: string): { value: string } | undefined };
    locals:  Record<string, any>;
}

export const ANONYMOUS_USER: RequestUser = Object.freeze({ auth_token: false, user: false }) as RequestUser

const LOCALS_KEY = 'request_user'

/** Decode a session token without verifying it. Throws when it isn't a JWT. */
export function decode_user(token: string): User {
    return jose.decodeJwt(token) as unknown as User
}

export function read_request_user(auth_token: string | undefined | null): RequestUser {
    if (!auth_token) return ANONYMOUS_USER

    try {
        return { auth_token, user: decode_user(auth_token) }
    } catch {
        // A cookie that isn't a JWT is a signed-out visitor, not a 500.
        return ANONYMOUS_USER
    }
}

/** Decoded once per request and kept on Astro.locals. */
export function get_request_user(astro: AstroLike): RequestUser {
    if (!astro.locals[LOCALS_KEY]) {
        const auth_token = astro.cookies.has('auth_token') ? astro.cookies.get('auth_token')?.value : undefined
        astro.locals[LOCALS_KEY] = read_request_user(auth_token)
    }

    return astro.locals[LOCALS_KEY]
}

/** The guest (friend) session, which uses its own cookie. */
export function get_guest_user(astro: AstroLike): RequestUser {
    return read_request_user(astro.cookies.has('guest_auth_token') ? astro.cookies.get('guest_auth_token')?.value : undefined)
}
