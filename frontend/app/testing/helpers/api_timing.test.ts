// @vitest-environment node
import { afterEach, expect, test, vi } from 'vitest'

import {
    count_rounds,
    format_api_timing,
    log_api_timing_on_finish,
    new_api_timing_store,
    run_with_api_timing,
    start_api_timing,
    timing_endpoint,
} from '@helpers/api_timing'
import { api_request } from '@helpers/api.minmatar.org/client'

afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
})

const entry = (start: number, end: number) => ({ endpoint: '/api/x', start, end, status: 200 })

test('ids in the path collapse to :id and the query is dropped', () => {
    expect(timing_endpoint('http://api/api/fleets/92221/members?x=1')).toBe('/api/fleets/:id/members')
    expect(timing_endpoint('http://api/api/users/me/gates')).toBe('/api/users/me/gates')
})

test('overlapping calls are one round, sequential calls are separate rounds', () => {
    expect(count_rounds([])).toBe(0)
    expect(count_rounds([entry(0, 10), entry(2, 8), entry(5, 20)])).toBe(1)
    expect(count_rounds([entry(0, 10), entry(10, 20), entry(25, 30)])).toBe(3)
    expect(count_rounds([entry(10, 20), entry(0, 15), entry(30, 40)])).toBe(2)
})

test('nothing is recorded outside a store', () => {
    const record = start_api_timing('http://api/api/users/me/gates')
    expect(() => record(200)).not.toThrow()
})

test('api_request calls are recorded inside a store, including failures', async () => {
    vi.spyOn(console, 'log').mockImplementation(() => {})
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn(async (url: string) =>
        url.endsWith('/fail') ? new Response('{}', { status: 502 }) : new Response('{"ok":true}', { status: 200 })
    ))

    const store = new_api_timing_store()
    await run_with_api_timing(store, async () => {
        await Promise.all([api_request('http://api/api/a/1'), api_request('http://api/api/b')])
        await api_request('http://api/api/fail').catch(() => null)
    })

    expect(store.entries.map((e) => [e.endpoint, e.status]).sort()).toEqual([
        ['/api/a/:id', 200],
        ['/api/b', 200],
        ['/api/fail', 502],
    ])
    expect(count_rounds(store.entries)).toBe(2)
    expect(format_api_timing('GET', '/x/', store)).toMatch(/^\[api-timing\] GET \/x\/ calls=3 rounds=2 /)
})

test('the log line is written once the body has streamed, and the body is unchanged', async () => {
    const log = vi.spyOn(console, 'log').mockImplementation(() => {})
    const store = new_api_timing_store()
    const response = log_api_timing_on_finish(
        new Response('<html>hi</html>', { status: 201, headers: { 'X-Test': '1' } }),
        'GET', '/page/', store,
    )

    expect(log).not.toHaveBeenCalled()
    expect(response.status).toBe(201)
    expect(response.headers.get('X-Test')).toBe('1')
    expect(await response.text()).toBe('<html>hi</html>')
    expect(log).toHaveBeenCalledTimes(1)
    expect(log.mock.calls[0][0]).toMatch(/^\[api-timing\] GET \/page\/ calls=0/)
})
