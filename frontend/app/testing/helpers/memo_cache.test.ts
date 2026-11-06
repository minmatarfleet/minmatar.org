// @vitest-environment node
import { afterEach, expect, test, vi } from 'vitest'

import { create_memo_cache, ttl_ms_from_env } from '@helpers/memo_cache'

afterEach(() => {
    vi.unstubAllEnvs()
})

function clock(start = 1_000) {
    let t = start
    return { now: () => t, advance: (ms: number) => { t += ms } }
}

test('a hit within the TTL does not call load again', async () => {
    const c = clock()
    const cache = create_memo_cache<number>(10, c.now)
    const load = vi.fn(async () => 1)

    expect(await cache.get('k', 1000, load)).toBe(1)
    c.advance(999)
    expect(await cache.get('k', 1000, load)).toBe(1)
    expect(load).toHaveBeenCalledTimes(1)
})

test('after the TTL the value is loaded again', async () => {
    const c = clock()
    const cache = create_memo_cache<number>(10, c.now)
    let n = 0
    const load = vi.fn(async () => ++n)

    expect(await cache.get('k', 1000, load)).toBe(1)
    c.advance(1000)
    expect(await cache.get('k', 1000, load)).toBe(2)
    expect(load).toHaveBeenCalledTimes(2)
})

test('a TTL of 0 never caches', async () => {
    const cache = create_memo_cache<number>()
    const load = vi.fn(async () => 1)

    await cache.get('k', 0, load)
    await cache.get('k', 0, load)
    expect(load).toHaveBeenCalledTimes(2)
    expect(cache.size).toBe(0)
})

test('concurrent misses share one load', async () => {
    const cache = create_memo_cache<number>()
    let resolve!: (v: number) => void
    const load = vi.fn(() => new Promise<number>((r) => { resolve = r }))

    const a = cache.get('k', 1000, load)
    const b = cache.get('k', 1000, load)
    resolve(7)
    expect(await Promise.all([a, b])).toEqual([7, 7])
    expect(load).toHaveBeenCalledTimes(1)
})

test('failures reach every waiting caller and are not cached', async () => {
    const cache = create_memo_cache<number>()
    let fail = true
    const load = vi.fn(async () => {
        if (fail) throw new Error('backend down')
        return 3
    })

    const results = await Promise.allSettled([cache.get('k', 1000, load), cache.get('k', 1000, load)])
    expect(results.map((r) => r.status)).toEqual(['rejected', 'rejected'])
    expect(load).toHaveBeenCalledTimes(1)

    fail = false
    expect(await cache.get('k', 1000, load)).toBe(3)
    expect(load).toHaveBeenCalledTimes(2)
})

test('different keys are separate', async () => {
    const cache = create_memo_cache<string>()
    expect(await cache.get('a', 1000, async () => 'A')).toBe('A')
    expect(await cache.get('b', 1000, async () => 'B')).toBe('B')
})

test('the least recently used key is dropped past max_entries', async () => {
    const cache = create_memo_cache<string>(2)
    const load = (v: string) => vi.fn(async () => v)

    await cache.get('a', 1000, load('A'))
    await cache.get('b', 1000, load('B'))
    await cache.get('a', 1000, load('A2'))   // touch a: b is now oldest
    await cache.get('c', 1000, load('C'))

    expect(cache.size).toBe(2)
    expect(await cache.get('a', 1000, load('A3'))).toBe('A')
    expect(await cache.get('b', 1000, load('B2'))).toBe('B2')
})

test('TTL from env: seconds to ms, 0 or junk turns it off, tests default to 0', () => {
    vi.stubEnv('X_TTL', '60')
    expect(ttl_ms_from_env('X_TTL', 5)).toBe(60_000)
    vi.stubEnv('X_TTL', '0')
    expect(ttl_ms_from_env('X_TTL', 5)).toBe(0)
    vi.stubEnv('X_TTL', 'nope')
    expect(ttl_ms_from_env('X_TTL', 5)).toBe(0)
    vi.stubEnv('X_TTL', '')
    expect(ttl_ms_from_env('X_TTL', 5)).toBe(0) // VITEST is set here
    vi.stubEnv('VITEST', '')
    expect(ttl_ms_from_env('X_TTL', 5)).toBe(5_000)
})
