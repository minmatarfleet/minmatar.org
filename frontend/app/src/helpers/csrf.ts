import crypto from 'crypto'
import { parse } from 'cookie'

export function generate_csrf_token(): string {
    return crypto.randomBytes(32).toString('hex')
}

export function check_csrf(request) {
    const cookies = parse(request.headers.get('cookie') || '')
    const csrfFromCookie = cookies.csrf
    const csrfFromHeader = request.headers.get('x-csrf-token')

    if (!csrfFromCookie || !csrfFromHeader || csrfFromCookie !== csrfFromHeader)
        throw new Error('Invalid CSRF token')
}