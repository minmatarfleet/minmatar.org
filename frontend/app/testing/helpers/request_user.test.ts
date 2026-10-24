import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it, vi } from 'vitest'

import { ANONYMOUS_USER, get_guest_user, get_request_user, read_request_user } from '@helpers/request_user'
import { login_redirect, login_url } from '@helpers/http_responses'

const SRC = join(__dirname, '../../src')

function token(payload: Record<string, unknown>) {
    const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString('base64url')
    return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(payload)}.signature`
}

function astro(cookies: Record<string, string> = {}) {
    const get = vi.fn((name: string) => (name in cookies ? { value: cookies[name] } : undefined))
    return {
        cookies: { has: (name: string) => name in cookies, get },
        locals: {} as Record<string, any>,
    }
}

function source_files(dir: string): string[] {
    return readdirSync(dir).flatMap((name) => {
        const path = join(dir, name)
        if (statSync(path).isDirectory()) return source_files(path)
        return /\.(astro|ts)$/.test(name) ? [path] : []
    })
}

function offenders(pattern: RegExp, allowed: string[] = []) {
    return source_files(SRC)
        .map((file) => relative(SRC, file))
        .filter((file) => !allowed.includes(file))
        .filter((file) => pattern.test(readFileSync(join(SRC, file), 'utf8')))
}

/** What pages/redirects/auth_init.astro does with the login URL. */
function return_target(location: string) {
    return new URL(location, 'https://my.minmatar.org').searchParams.get('redirect_url')
}

describe('get_request_user', () => {
    it('is anonymous without a session cookie', () => {
        expect(get_request_user(astro())).toBe(ANONYMOUS_USER)
    })

    it('decodes the session token', () => {
        const session = token({ user_id: 42, username: 'pilot', is_superuser: false })
        const { auth_token, user } = get_request_user(astro({ auth_token: session }))

        expect(auth_token).toBe(session)
        expect(user && user.user_id).toBe(42)
    })

    it('reads the cookie once per request', () => {
        const request = astro({ auth_token: token({ user_id: 1 }) })

        const first = get_request_user(request)
        const second = get_request_user(request)

        expect(second).toBe(first)
        expect(request.cookies.get).toHaveBeenCalledTimes(1)
    })

    it('treats a cookie that is not a JWT as signed out', () => {
        expect(get_request_user(astro({ auth_token: 'not-a-jwt' }))).toEqual({ auth_token: false, user: false })
        expect(read_request_user('')).toBe(ANONYMOUS_USER)
    })

    it('keeps the guest session separate', () => {
        const guest = token({ user_id: 9 })
        const request = astro({ guest_auth_token: guest })

        expect(get_request_user(request)).toBe(ANONYMOUS_USER)
        expect(get_guest_user(request).auth_token).toBe(guest)
    })
})

describe('login_redirect', () => {
    const page = (href: string, headers: Record<string, string> = {}) => ({
        request: new Request(href, { headers }),
        url: new URL(href),
    })

    it('sends the visitor to the login notice', () => {
        const response = login_redirect(page('https://my.minmatar.org/fleets/upcoming/'))

        expect(response.status).toBe(302)
        expect(response.headers.get('Location')).toMatch(/^\/redirects\/auth_init\?redirect_url=/)
    })

    it('keeps every query parameter for the way back', () => {
        const href = 'https://my.minmatar.org/market/buyback/order?type_id=34&quantity=2&note=a%26b#top'
        const response = login_redirect(page(href))

        expect(return_target(response.headers.get('Location') as string)).toBe(href)
    })

    it('the old unencoded form lost everything after the first &', () => {
        const href = 'https://my.minmatar.org/x/?a=1&b=2'
        expect(return_target(`/redirects/auth_init?redirect_url=${href}`)).toBe('https://my.minmatar.org/x/?a=1')
        expect(return_target(login_url({ url: new URL(href) }))).toBe(href)
    })
})

describe('the session preamble lives in one place', () => {
    it('only helpers/request_user.ts decodes the JWT', () => {
        expect(offenders(/from 'jose'|decodeJwt\(/, ['helpers/request_user.ts'])).toEqual([])
    })

    it('nothing else reads the auth_token cookie', () => {
        expect(offenders(/cookies\.get\(\s*['"]auth_token['"]\s*\)/, ['helpers/request_user.ts'])).toEqual([])
    })

    it('no login URL is built by hand', () => {
        expect(offenders(/redirect_url=\$\{Astro\.url\}/)).toEqual([])
        expect(offenders(/\/redirects\/auth_init'\)\}\?redirect_url=/, ['helpers/http_responses.ts'])).toEqual([])
    })

    it('no page or partial reads the JWT superuser or staff claim', () => {
        const allowed = [
            // The gate context carries the claim for legacy expressions.
            'helpers/gates.ts',
            // content.manage's legacy expression (superuser or Thinkspeak).
            'helpers/thinkspeak.ts',
            // Shows "Administrator" among the account's own roles; not access.
            'pages/account.astro',
        ]
        expect(offenders(/\.is_superuser\b|\bis_staff\b/, allowed)).toEqual([])
    })
})
