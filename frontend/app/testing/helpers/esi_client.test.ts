import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clear_esi_cache, ESI_COMPATIBILITY_DATE } from '@helpers/api.eveonline/client'
import { get_alliance_by_id } from '@helpers/api.eveonline/alliances'
import { get_character_by_id } from '@helpers/api.eveonline/characters'
import { get_route } from '@helpers/api.eveonline/routes'
import { get_names_and_categories_by_ids } from '@helpers/api.eveonline/universe'

function mock_fetch(make: () => Response) {
    const fetch_mock = vi.fn(async () => make())
    vi.stubGlobal('fetch', fetch_mock)
    return fetch_mock
}

describe('ESI client', () => {
    beforeEach(() => clear_esi_cache())
    afterEach(() => vi.unstubAllGlobals())

    it('identifies itself and pins the compatibility date', async () => {
        const fetch_mock = mock_fetch(() => new Response('{"name":"Bob"}'))
        await get_character_by_id(90000001)

        const [ url, init ] = fetch_mock.mock.calls[0] as unknown as [string, RequestInit]
        expect(url).toMatch(/\/characters\/90000001$/)
        expect(init.headers).toMatchObject({
            'User-Agent': expect.stringContaining('minmatar.org'),
            'X-Compatibility-Date': ESI_COMPATIBILITY_DATE,
        })
    })

    it('posts JSON bodies', async () => {
        const fetch_mock = mock_fetch(() => new Response('[]'))
        await get_names_and_categories_by_ids([1, 2])

        const init = fetch_mock.mock.calls[0][1] as RequestInit
        expect(init.method).toBe('POST')
        expect(init.body).toBe('[1,2]')
    })

    it('puts the status in cause so ErrorRefetch does not treat it as a timeout', async () => {
        mock_fetch(() => new Response('{"error":"not found"}', { status: 404 }))

        await expect(get_character_by_id(1)).rejects.toMatchObject({
            message: 'Error fetching character: HTTP error! Status: 404',
            cause: 404,
        })
    })

    it('returns an empty route when there is none', async () => {
        mock_fetch(() => new Response('{"error":"No route found"}', { status: 404 }))
        expect(await get_route(30002537, 30000142)).toEqual([])
    })

    it('caches alliance lookups but not failures', async () => {
        const fetch_mock = mock_fetch(() => new Response('{"name":"Minmatar Fleet Alliance"}'))
        await get_alliance_by_id(99011978)
        await get_alliance_by_id(99011978)
        expect(fetch_mock).toHaveBeenCalledTimes(1)

        const failing = mock_fetch(() => new Response('', { status: 502 }))
        await expect(get_alliance_by_id(1)).rejects.toMatchObject({ cause: 502 })
        await expect(get_alliance_by_id(1)).rejects.toMatchObject({ cause: 502 })
        expect(failing).toHaveBeenCalledTimes(2)
    })
})
