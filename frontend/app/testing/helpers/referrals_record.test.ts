import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@helpers/env', () => ({
    get_shared_secret: () => 'frontend-secret',
}))

import { record_referral } from '@helpers/api.minmatar.org/referrals'

describe('record_referral', () => {
    afterEach(() => vi.unstubAllGlobals())

    it('sends the shared secret so the API accepts the record', async () => {
        const fetch_mock = vi.fn(async () => new Response('"OK"', { status: 201 }))
        vi.stubGlobal('fetch', fetch_mock)
        vi.spyOn(console, 'log').mockImplementation(() => {})

        await expect(record_referral('Corps', 42, '203.0.113.7')).resolves.toBe(true)

        expect(fetch_mock).toHaveBeenCalledOnce()
        const [url, init] = fetch_mock.mock.calls[0] as unknown as [string, RequestInit]
        expect(url).toMatch(/\/api\/referrals$/)
        expect(init.method).toBe('POST')
        expect((init.headers as Record<string, string>)['X-Shared-Secret']).toBe('frontend-secret')
        expect(JSON.parse(init.body as string)).toEqual({
            page: 'Corps',
            user_id: 42,
            client_ip: '203.0.113.7',
        })
    })
})
