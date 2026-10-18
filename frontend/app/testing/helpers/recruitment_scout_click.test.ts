import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@helpers/env', () => ({
    get_shared_secret: () => 'frontend-secret',
}))

import { record_scout_click } from '@helpers/api.minmatar.org/recruitment'

describe('record_scout_click', () => {
    afterEach(() => vi.unstubAllGlobals())

    it('sends the shared secret so the API accepts the click', async () => {
        const fetch_mock = vi.fn(async () => new Response('"OK"', { status: 201 }))
        vi.stubGlobal('fetch', fetch_mock)

        await record_scout_click('k3x9qa', 'discord', '203.0.113.7', 'Mozilla/5.0')

        expect(fetch_mock).toHaveBeenCalledOnce()
        const [url, init] = fetch_mock.mock.calls[0] as unknown as [string, RequestInit]
        expect(url).toMatch(/\/api\/recruitment\/scout\/clicks$/)
        expect(init.method).toBe('POST')
        expect((init.headers as Record<string, string>)['X-Shared-Secret']).toBe('frontend-secret')
        expect(JSON.parse(init.body as string)).toEqual({
            code: 'k3x9qa',
            target: 'discord',
            client_ip: '203.0.113.7',
            user_agent: 'Mozilla/5.0',
        })
    })

    it('never throws when the API is unreachable', async () => {
        vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('down') }))
        vi.spyOn(console, 'log').mockImplementation(() => {})

        await expect(record_scout_click('k3x9qa', 'discord', '', '')).resolves.toBeUndefined()
    })
})
