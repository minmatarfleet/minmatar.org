import { afterEach, describe, expect, it, vi } from 'vitest'

import { create_fleet_srp } from '@helpers/api.minmatar.org/srp'

function capture_body() {
    const fetch_mock = vi.fn(async () => new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetch_mock)
    return () => JSON.parse(fetch_mock.mock.calls[0][1].body)
}

describe('create_fleet_srp', () => {
    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it('sends the combat log under the key the backend reads', async () => {
        const body = capture_body()

        await create_fleet_srp('token', {
            external_killmail_link: 'https://esi.evetech.net/killmails/1/abc/',
            fleet_id: 7,
            combat_log_id: 42,
            is_corp_ship: false,
        })

        expect(body()).toMatchObject({ fleet_id: 7, combat_log_id: 42 })
        expect(body()).not.toHaveProperty('combatlog_id')
    })

    it('leaves the combat log out when there is none', async () => {
        const body = capture_body()

        await create_fleet_srp('token', {
            external_killmail_link: 'https://esi.evetech.net/killmails/1/abc/',
            is_corp_ship: true,
        })

        expect(body()).not.toHaveProperty('combat_log_id')
        expect(body()).not.toHaveProperty('fleet_id')
    })
})
