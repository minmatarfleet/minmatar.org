// @vitest-environment node
import { beforeEach, expect, test, vi } from 'vitest'

const api = vi.hoisted(() => ({
    get_fleets_v3: vi.fn(),
    get_fleets_metrics: vi.fn(),
    get_fleet_commander_metrics: vi.fn(),
    get_fleet_ship_volunteers: vi.fn(),
    get_fleet_results: vi.fn(),
    get_doctrine_by_id: vi.fn(),
    get_characters_summary_sorted: vi.fn(),
    get_tribe_group: vi.fn(),
}))

vi.mock('@helpers/api.minmatar.org/fleets', async (original) => ({
    ...(await original<typeof import('@helpers/api.minmatar.org/fleets')>()),
    get_fleets_v3: api.get_fleets_v3,
    get_fleets_metrics: api.get_fleets_metrics,
    get_fleet_commander_metrics: api.get_fleet_commander_metrics,
    get_fleet_ship_volunteers: api.get_fleet_ship_volunteers,
    get_fleet_results: api.get_fleet_results,
}))
vi.mock('@helpers/fetching/doctrines', () => ({
    fetch_doctrine_by_id: async (id: number) => {
        const doctrine = await api.get_doctrine_by_id(id)
        return { id: doctrine.id, name: doctrine.name, primary_fittings: [] }
    },
}))
vi.mock('@helpers/fetching/characters', () => ({
    get_characters_summary_sorted: api.get_characters_summary_sorted,
}))
vi.mock('@helpers/api.minmatar.org/tribes', () => ({
    get_tribe_group: api.get_tribe_group,
}))

import { fetch_fleet_history, fetch_fleet_schedule } from '@helpers/fetching/fleet_schedule'
import { fetch_fleets_auth } from '@helpers/fetching/fleets'

const in_hours = (h: number) => new Date(Date.now() + h * 3_600_000).toISOString()

function fleet(id: number, extra: Record<string, unknown> = {}) {
    return {
        id,
        fleet_commander: 1,
        fleet_commander_character_id: 100 + id,
        fleet_commander_name: `FC ${id}`,
        start_time: in_hours(id),
        status: 'pending',
        doctrine_id: id * 10,
        ...extra,
    }
}

/** A promise the test resolves by hand, to see what starts before it settles. */
function deferred<T>() {
    let resolve!: (value: T) => void
    let reject!: (reason: unknown) => void
    const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
    return { promise, resolve, reject }
}

beforeEach(() => {
    for (const fn of Object.values(api)) fn.mockReset()
    vi.spyOn(console, 'log').mockImplementation(() => {})
    api.get_fleets_v3.mockResolvedValue([fleet(1), fleet(2, { host_group: { id: 5, tribe_id: 3, name: 'G' } })])
    api.get_fleets_metrics.mockResolvedValue([])
    api.get_fleet_commander_metrics.mockResolvedValue([])
    api.get_fleet_ship_volunteers.mockResolvedValue([])
    api.get_fleet_results.mockResolvedValue([])
    api.get_doctrine_by_id.mockImplementation(async (id: number) => ({ id, name: `D${id}` }))
    api.get_characters_summary_sorted.mockResolvedValue({ characters: [] })
    api.get_tribe_group.mockResolvedValue({ is_member: true })
})

test('the fleets, their metrics and the FC metrics are all requested before any of them answers', async () => {
    const fc = deferred<unknown[]>()
    const fleets = deferred<unknown[]>()
    const metrics = deferred<unknown[]>()
    api.get_fleet_commander_metrics.mockReturnValue(fc.promise)
    api.get_fleets_v3.mockReturnValue(fleets.promise)
    api.get_fleets_metrics.mockReturnValue(metrics.promise)

    const schedule = fetch_fleet_schedule('token')
    await new Promise((r) => setTimeout(r, 0))

    expect(api.get_fleet_commander_metrics).toHaveBeenCalledTimes(1)
    expect(api.get_fleets_v3).toHaveBeenCalledTimes(1)
    expect(api.get_fleets_metrics).toHaveBeenCalledTimes(1)

    fc.resolve([])
    fleets.resolve([fleet(1)])
    metrics.resolve([])
    expect((await schedule).fleets.map((f) => f.id)).toEqual([1])
})

test('the doctrines and the next fleet signups are requested together, each once', async () => {
    const doctrine = deferred<{ id: number; name: string }>()
    api.get_doctrine_by_id.mockReturnValue(doctrine.promise)

    const schedule = fetch_fleet_schedule('token')
    await new Promise((r) => setTimeout(r, 0))
    expect(api.get_fleet_ship_volunteers).toHaveBeenCalledTimes(1)
    expect(api.get_characters_summary_sorted).toHaveBeenCalledTimes(1)

    doctrine.resolve({ id: 10, name: 'D10' })
    const result = await schedule
    expect(result.next?.id).toBe(1)
    expect(api.get_fleet_commander_metrics).toHaveBeenCalledTimes(1)
    expect(api.get_fleets_v3).toHaveBeenCalledTimes(1)
    expect(api.get_fleets_metrics).toHaveBeenCalledTimes(1)
})

test('with ?host=mine, doctrines are fetched for the filtered fleets only', async () => {
    api.get_tribe_group.mockResolvedValue({ is_member: true })

    const result = await fetch_fleet_schedule('token', 'mine')

    expect(result.fleets.map((f) => f.id)).toEqual([2])
    expect(api.get_doctrine_by_id.mock.calls.map(([id]) => id)).toEqual([20])
})

test('a failed signups lookup still leaves the schedule with 0 signups', async () => {
    api.get_fleet_ship_volunteers.mockRejectedValue(new Error('boom'))

    const result = await fetch_fleet_schedule('token')

    expect(result.next_signups).toBe(0)
    expect(Object.keys(result.doctrines)).toEqual(['10', '20'])
})

test('when the FC metrics and the fleets both fail, the FC metrics error is thrown, as before', async () => {
    api.get_fleet_commander_metrics.mockRejectedValue(new Error('fc metrics failed'))
    api.get_fleets_v3.mockRejectedValue(new Error('fleets failed'))

    await expect(fetch_fleet_schedule('token')).rejects.toThrow('fc metrics failed')
    await expect(fetch_fleet_history('token')).rejects.toThrow('fc metrics failed')
})

test('when only the fleets fail, that error is thrown', async () => {
    api.get_fleets_v3.mockRejectedValue(new Error('fleets failed'))

    await expect(fetch_fleet_schedule('token')).rejects.toThrow('fleets failed')
})

test('fetch_fleets_auth throws the fleets error before the metrics error, as before', async () => {
    api.get_fleets_v3.mockRejectedValue(new Error('fleets failed'))
    api.get_fleets_metrics.mockRejectedValue(new Error('metrics failed'))

    await expect(fetch_fleets_auth('token', true)).rejects.toThrow('fleets failed')
})

test('fetch_fleets_auth without FC metrics fetches them itself, once', async () => {
    await fetch_fleets_auth('token', false)

    expect(api.get_fleet_commander_metrics).toHaveBeenCalledTimes(1)
    expect(api.get_fleets_metrics).toHaveBeenCalledTimes(1)
})

test('simplified fetch_fleets_auth asks for no metrics', async () => {
    await fetch_fleets_auth('token', true, true)

    expect(api.get_fleet_commander_metrics).not.toHaveBeenCalled()
    expect(api.get_fleets_metrics).not.toHaveBeenCalled()
})
