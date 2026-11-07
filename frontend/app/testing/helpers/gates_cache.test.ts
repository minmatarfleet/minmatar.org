import { afterEach, beforeEach, expect, test, vi } from 'vitest'

vi.mock('@helpers/api.minmatar.org/gates', () => ({
    get_user_gates: vi.fn(),
}))

import { get_user_gates } from '@helpers/api.minmatar.org/gates'
import { can, clear_gates_cache, get_gates, set_gates_cache_ttl } from '@helpers/gates'

function token(payload: Record<string, unknown>) {
    const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString('base64url')
    return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(payload)}.signature`
}

/** A fresh request: get_gates memoizes per request through locals. */
function request(cookie?: string) {
    return {
        cookies: {
            has: (name: string) => name === 'auth_token' && cookie !== undefined,
            get: (name: string) => (name === 'auth_token' && cookie !== undefined ? { value: cookie } : undefined),
        },
        locals: {} as Record<string, any>,
    }
}

const PILOT = token({ user_id: 7, username: 'pilot', is_superuser: false })
const OTHER = token({ user_id: 8, username: 'other', is_superuser: false })
const gates_with = (permissions: string[]) => ({
    features: [],
    legacy: { permissions },
    gate_source: 'legacy',
    led_corporations: [],
})

beforeEach(() => {
    clear_gates_cache()
    set_gates_cache_ttl(60_000)
    vi.mocked(get_user_gates).mockReset()
})

afterEach(() => {
    vi.useRealTimers()
    set_gates_cache_ttl(null)
    clear_gates_cache()
})

test('requests within the TTL share one gates call', async () => {
    vi.mocked(get_user_gates).mockResolvedValue(gates_with(['fleets.view_evefleet']) as any)

    const first = await get_gates(request(PILOT))
    const second = await get_gates(request(PILOT))

    expect(can(first, 'fleets.view')).toBe(true)
    expect(can(second, 'fleets.view')).toBe(true)
    expect(get_user_gates).toHaveBeenCalledTimes(1)
})

test('each request still gets its own context (mismatch reports are per request)', async () => {
    vi.mocked(get_user_gates).mockResolvedValue(gates_with([]) as any)

    const first = await get_gates(request(PILOT))
    const second = await get_gates(request(PILOT))

    expect(first).not.toBe(second)
    expect(first.reported).not.toBe(second.reported)
})

test('a page and its partials loading together make one call', async () => {
    let resolve!: (value: unknown) => void
    vi.mocked(get_user_gates).mockReturnValue(new Promise((r) => { resolve = r }) as any)

    const pending = [get_gates(request(PILOT)), get_gates(request(PILOT)), get_gates(request(PILOT))]
    resolve(gates_with(['fleets.view_evefleet']))
    const contexts = await Promise.all(pending)

    expect(contexts.every((ctx) => can(ctx, 'fleets.view'))).toBe(true)
    expect(get_user_gates).toHaveBeenCalledTimes(1)
})

test('after the TTL the gates are fetched again', async () => {
    vi.useFakeTimers()
    vi.mocked(get_user_gates)
        .mockResolvedValueOnce(gates_with([]) as any)
        .mockResolvedValueOnce(gates_with(['fleets.view_evefleet']) as any)

    expect(can(await get_gates(request(PILOT)), 'fleets.view')).toBe(false)
    vi.advanceTimersByTime(60_000)
    expect(can(await get_gates(request(PILOT)), 'fleets.view')).toBe(true)
    expect(get_user_gates).toHaveBeenCalledTimes(2)
})

test('a failed call is not cached and falls back to no permissions, as before', async () => {
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.mocked(get_user_gates)
        .mockRejectedValueOnce(new Error('backend down'))
        .mockResolvedValueOnce(gates_with(['fleets.view_evefleet']) as any)

    expect(can(await get_gates(request(PILOT)), 'fleets.view')).toBe(false)
    expect(can(await get_gates(request(PILOT)), 'fleets.view')).toBe(true)
    expect(get_user_gates).toHaveBeenCalledTimes(2)
})

test('different tokens are cached separately', async () => {
    vi.mocked(get_user_gates).mockImplementation(async (t: string) =>
        gates_with(t === PILOT ? ['fleets.view_evefleet'] : []) as any)

    expect(can(await get_gates(request(PILOT)), 'fleets.view')).toBe(true)
    expect(can(await get_gates(request(OTHER)), 'fleets.view')).toBe(false)
    expect(get_user_gates).toHaveBeenCalledTimes(2)
})

test('a TTL of 0 fetches on every request', async () => {
    set_gates_cache_ttl(0)
    vi.mocked(get_user_gates).mockResolvedValue(gates_with([]) as any)

    await get_gates(request(PILOT))
    await get_gates(request(PILOT))
    expect(get_user_gates).toHaveBeenCalledTimes(2)
})

test('anonymous requests never call the backend', async () => {
    await get_gates(request())
    expect(get_user_gates).not.toHaveBeenCalled()
})
