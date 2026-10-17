import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@helpers/api.minmatar.org/fleets', () => ({
    get_fleet_by_id: vi.fn(),
    get_fleets_v3: vi.fn(),
    get_fleets_metrics: vi.fn(),
    get_fleet_commander_metrics: vi.fn(),
    get_fleet_users: vi.fn(),
}))
vi.mock('@helpers/fetching/characters', () => ({
    get_user_character: vi.fn(),
    get_users_character: vi.fn(),
}))
vi.mock('@helpers/fetching/doctrines', () => ({ fetch_doctrine_by_id: vi.fn() }))
vi.mock('@helpers/api.minmatar.org/campaigns', () => ({ get_campaign: vi.fn() }))
vi.mock('@helpers/api.eveonline/routes', () => ({ get_route: vi.fn() }))
vi.mock('@helpers/sde/map', () => ({ get_system_sun_type_id: vi.fn() }))
vi.mock('@helpers/date', () => ({ time_diff_text: vi.fn() }))

import { get_fleet_by_id } from '@helpers/api.minmatar.org/fleets'
import { get_user_character } from '@helpers/fetching/characters'
import { fetch_doctrine_by_id } from '@helpers/fetching/doctrines'
import { get_campaign } from '@helpers/api.minmatar.org/campaigns'
import { fetch_fleet_by_id } from '@helpers/fetching/fleets'
import { settled_value } from '@helpers/settled'

const FLEET = {
    id: 7,
    description: 'Roam',
    objective: 'Kill things',
    fleet_commander: 11,
    doctrine_id: 3,
    campaign_slug: 'tama',
    campaign_id: 2,
    location: 'Amamake - Freeport',
    start_time: '2026-10-17T20:00:00Z',
    type: 'strategic',
    tracking: null,
    audience: 'Alliance',
    disable_motd: false,
    hide_volunteers: false,
    status: 'pending',
    aar_link: null,
    roam_report_url: null,
}
const FC = { character_id: 90, character_name: 'Commander' }
const DOCTRINE = { id: 3, name: 'Hurricanes' }

/** A promise the test resolves or rejects by hand. */
function deferred<T>() {
    let resolve!: (value: T) => void
    let reject!: (reason: unknown) => void
    const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
    return { promise, resolve, reject }
}

describe('fetch_fleet_by_id', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.mocked(get_fleet_by_id).mockResolvedValue(FLEET as any)
        vi.mocked(get_user_character).mockResolvedValue(FC as any)
        vi.mocked(fetch_doctrine_by_id).mockResolvedValue(DOCTRINE as any)
        vi.mocked(get_campaign).mockResolvedValue({ name: 'Tama push' } as any)
    })

    it('builds the same fleet as before', async () => {
        expect(await fetch_fleet_by_id('token', 7)).toEqual({
            id: 7,
            description: 'Roam',
            objective: 'Kill things',
            fleet_commander_id: 90,
            fleet_commander_name: 'Commander',
            location: 'Amamake - Freeport',
            start_time: '2026-10-17T20:00:00Z',
            type: 'strategic',
            doctrine: DOCTRINE,
            tracking: null,
            audience: 'Alliance',
            disable_motd: false,
            hide_volunteers: false,
            status: 'pending',
            aar_link: '',
            roam_report_url: '',
            campaign_id: 2,
            campaign_slug: 'tama',
            campaign_name: 'Tama push',
        })
        expect(get_campaign).toHaveBeenCalledWith('tama', 'token')
    })

    it('asks for the FC, doctrine and campaign at the same time', async () => {
        const fc = deferred<any>()
        const doctrine = deferred<any>()
        const campaign = deferred<any>()
        vi.mocked(get_user_character).mockReturnValue(fc.promise)
        vi.mocked(fetch_doctrine_by_id).mockReturnValue(doctrine.promise)
        vi.mocked(get_campaign).mockReturnValue(campaign.promise)

        const result = fetch_fleet_by_id('token', 7)
        await vi.waitFor(() => expect(get_campaign).toHaveBeenCalled())

        // All three started while none had answered: one round trip, not three.
        expect(get_user_character).toHaveBeenCalledWith(11)
        expect(fetch_doctrine_by_id).toHaveBeenCalledWith(3)

        fc.resolve(FC)
        doctrine.resolve(DOCTRINE)
        campaign.resolve({ name: 'Tama push' })
        expect((await result).campaign_name).toBe('Tama push')
    })

    it('skips lookups the fleet has no id for', async () => {
        vi.mocked(get_fleet_by_id).mockResolvedValue({ ...FLEET, fleet_commander: 0, doctrine_id: null, campaign_slug: null } as any)

        const fleet = await fetch_fleet_by_id('token', 7)

        expect(fleet.fleet_commander_id).toBe(0)
        expect(fleet.doctrine).toBeNull()
        expect(fleet.campaign_name).toBeNull()
        expect(get_user_character).not.toHaveBeenCalled()
        expect(fetch_doctrine_by_id).not.toHaveBeenCalled()
        expect(get_campaign).not.toHaveBeenCalled()
    })

    it('still keeps the slug when the campaign name is forbidden', async () => {
        vi.mocked(get_campaign).mockRejectedValue(new Error('Forbidden', { cause: 403 }))

        const fleet = await fetch_fleet_by_id('token', 7)

        expect(fleet.campaign_slug).toBe('tama')
        expect(fleet.campaign_name).toBeNull()
    })

    it('fails with the error the sequential version hit first', async () => {
        const doctrine_error = new Error('doctrine', { cause: 500 })
        vi.mocked(fetch_doctrine_by_id).mockRejectedValue(doctrine_error)
        await expect(fetch_fleet_by_id('token', 7)).rejects.toBe(doctrine_error)

        // The FC lookup came first, so its failure wins even if it answers last.
        const fc = deferred<any>()
        const fc_error = new Error('fc', { cause: 404 })
        vi.mocked(get_user_character).mockReturnValue(fc.promise)
        const result = fetch_fleet_by_id('token', 7)
        setTimeout(() => fc.reject(fc_error), 5)
        await expect(result).rejects.toBe(fc_error)
    })

    it('propagates a missing fleet', async () => {
        const missing = new Error('missing', { cause: 404 })
        vi.mocked(get_fleet_by_id).mockRejectedValue(missing)

        await expect(fetch_fleet_by_id('token', 7)).rejects.toBe(missing)
    })
})

describe('settled_value', () => {
    it('returns the value or rethrows the reason', async () => {
        const [ok, failed] = await Promise.allSettled([Promise.resolve(1), Promise.reject(new Error('no'))])
        expect(settled_value(ok)).toBe(1)
        expect(() => settled_value(failed)).toThrow('no')
    })
})
