// @vitest-environment node
import { beforeEach, expect, test, vi } from 'vitest'

const api = vi.hoisted(() => ({
    get_character_by_id: vi.fn(),
    get_character_skillsets: vi.fn(),
    get_corporation_by_id: vi.fn(),
    get_corporation_applications: vi.fn(),
    get_corporation_applications_by_id: vi.fn(),
    get_my_open_application: vi.fn(),
}))

vi.mock('@helpers/api.minmatar.org/characters', async (original) => ({
    ...(await original<typeof import('@helpers/api.minmatar.org/characters')>()),
    get_character_by_id: api.get_character_by_id,
    get_character_skillsets: api.get_character_skillsets,
}))
vi.mock('@helpers/api.minmatar.org/corporations', async (original) => ({
    ...(await original<typeof import('@helpers/api.minmatar.org/corporations')>()),
    get_corporation_by_id: api.get_corporation_by_id,
}))
vi.mock('@helpers/api.minmatar.org/applications', async (original) => ({
    ...(await original<typeof import('@helpers/api.minmatar.org/applications')>()),
    get_corporation_applications: api.get_corporation_applications,
    get_corporation_applications_by_id: api.get_corporation_applications_by_id,
    get_my_open_application: api.get_my_open_application,
}))

import { get_skillsets } from '@helpers/fetching/characters'
import { get_corporation_list_by_id_auth } from '@helpers/fetching/corporations'

const CORP = {
    corporation_id: 98000001,
    corporation_name: 'Test Corp',
    alliance_id: 99011978,
    alliance_name: 'Minmatar Fleet Alliance',
    type: 'alliance',
    active: true,
    trial: false,
}

function deferred<T>() {
    let resolve!: (value: T) => void
    const promise = new Promise<T>((res) => { resolve = res })
    return { promise, resolve }
}

beforeEach(() => {
    for (const fn of Object.values(api)) fn.mockReset()
    vi.spyOn(console, 'log').mockImplementation(() => {})
})

test('get_skillsets asks for the character and its skillsets together', async () => {
    const character = deferred<unknown>()
    api.get_character_by_id.mockReturnValue(character.promise)
    api.get_character_skillsets.mockResolvedValue([{ name: 'Rifter', progress: 1, missing_skills: [] }])

    const result = get_skillsets('token', 5)
    await new Promise((r) => setTimeout(r, 0))
    expect(api.get_character_skillsets).toHaveBeenCalledTimes(1)

    character.resolve({ character_id: 5, character_name: 'Pilot' })
    expect(await result).toMatchObject({ character_id: 5, character_name: 'Pilot', skillsets: [{ name: 'Rifter' }] })
})

test('get_skillsets throws the character error first when both fail, as before', async () => {
    api.get_character_by_id.mockRejectedValue(new Error('character failed'))
    api.get_character_skillsets.mockRejectedValue(new Error('skillsets failed'))

    await expect(get_skillsets('token', 5)).rejects.toThrow('character failed')
})

test('get_skillsets throws the skillsets error when only that fails', async () => {
    api.get_character_by_id.mockResolvedValue({ character_id: 5, character_name: 'Pilot' })
    api.get_character_skillsets.mockRejectedValue(new Error('skillsets failed'))

    await expect(get_skillsets('token', 5)).rejects.toThrow('skillsets failed')
})

test('the corporation, its applications and my open application start together', async () => {
    const corporation = deferred<unknown>()
    api.get_corporation_by_id.mockReturnValue(corporation.promise)
    api.get_corporation_applications.mockResolvedValue([])
    api.get_my_open_application.mockResolvedValue({ corporation_id: 98000002, corporation_name: 'Other Corp' })

    const result = get_corporation_list_by_id_auth('token', CORP.corporation_id, 7)
    await new Promise((r) => setTimeout(r, 0))
    expect(api.get_corporation_applications).toHaveBeenCalledWith('token', CORP.corporation_id)
    expect(api.get_my_open_application).toHaveBeenCalledTimes(1)

    corporation.resolve(CORP)
    expect(await result).toMatchObject({
        corporation_id: CORP.corporation_id,
        status: 'available',
        open_application_corporation_name: 'Other Corp',
    })
})

test('an applications failure still marks the corporation as error and annotates it, as before', async () => {
    api.get_corporation_by_id.mockResolvedValue(CORP)
    api.get_corporation_applications.mockRejectedValue(new Error('applications failed'))
    api.get_my_open_application.mockResolvedValue({ corporation_id: 98000002, corporation_name: 'Other Corp' })

    expect(await get_corporation_list_by_id_auth('token', CORP.corporation_id, 7)).toMatchObject({
        status: 'error',
        open_application_corporation_name: 'Other Corp',
    })
})

test('an open-application failure leaves the corporation unannotated, as before', async () => {
    api.get_corporation_by_id.mockResolvedValue(CORP)
    api.get_corporation_applications.mockResolvedValue([{ user_id: 7, application_id: 3, status: 'pending' }])
    api.get_corporation_applications_by_id.mockResolvedValue({ updated_at: '2026-11-01T00:00:00Z' })
    api.get_my_open_application.mockRejectedValue(new Error('open failed'))

    const result = await get_corporation_list_by_id_auth('token', CORP.corporation_id, 7)
    expect(result).toMatchObject({ status: 'pending', application_updated: '2026-11-01T00:00:00Z' })
    expect(result.open_application_corporation_name).toBeUndefined()
})

test('a corporation failure is still thrown', async () => {
    api.get_corporation_by_id.mockRejectedValue(new Error('corporation failed'))
    api.get_corporation_applications.mockRejectedValue(new Error('applications failed'))
    api.get_my_open_application.mockRejectedValue(new Error('open failed'))

    await expect(get_corporation_list_by_id_auth('token', CORP.corporation_id, 7)).rejects.toThrow('corporation failed')
})
