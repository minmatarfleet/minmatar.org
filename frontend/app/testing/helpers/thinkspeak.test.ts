import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@helpers/api.minmatar.org/tribes', () => ({
    get_tribes: vi.fn(async () => [{ id: 1, slug: 'pulse', name: 'Pulse' }]),
    get_tribe_groups: vi.fn(async () => [{ id: 2, code: 'pulse.thinkspeak', name: 'Thinkspeak' }]),
    get_memberships: vi.fn(),
}))

import { get_memberships } from '@helpers/api.minmatar.org/tribes'
import { ANONYMOUS_GATES, type GateContext } from '@helpers/gates'
import { can_manage_content } from '@helpers/thinkspeak'

function gates(overrides: Partial<GateContext> = {}): GateContext {
    return { ...ANONYMOUS_GATES, user_id: 7, reported: new Set(), ...overrides }
}

describe('can_manage_content', () => {
    beforeEach(() => vi.mocked(get_memberships).mockReset())

    // The inline check it replaced:
    // user && (is_superuser || (auth_token && is_thinkspeak_member(auth_token)))
    it.each([
        [false, false],
        [false, true],
        [true, false],
        [true, true],
    ])('legacy mode matches the old check (superuser %s, Thinkspeak %s)', async (is_superuser, member) => {
        vi.mocked(get_memberships).mockResolvedValue(member ? [{ status: 'active' }] as any : [])

        expect(await can_manage_content(gates({ is_superuser }), 'token')).toBe(is_superuser || member)
    })

    it('is closed to visitors without a session', async () => {
        expect(await can_manage_content(ANONYMOUS_GATES, false)).toBe(false)
        expect(get_memberships).not.toHaveBeenCalled()
    })

    it('features mode follows the feature only', async () => {
        const ctx = gates({ gate_source: 'features', is_superuser: true, features: [] })
        expect(await can_manage_content(ctx, 'token')).toBe(false)
        expect(await can_manage_content({ ...ctx, features: ['content.manage'] }, 'token')).toBe(true)
        expect(get_memberships).not.toHaveBeenCalled()
    })
})
