import { get_tribes, get_tribe_groups, get_memberships } from '@helpers/api.minmatar.org/tribes'
import { can_custom, legacy_superuser, type GateContext } from '@helpers/gates'

export const THINKSPEAK_GROUP_CODE = 'pulse.thinkspeak'
export const THINKSPEAK_GROUP_NAME = 'Thinkspeak'

/** Active Thinkspeak tribe-group membership for the authenticated user. */
export async function is_thinkspeak_member(access_token: string): Promise<boolean> {
    try {
        const tribes = await get_tribes()
        const pulse = tribes.find((tribe) => tribe.slug === 'pulse' || tribe.name === 'Pulse')
        if (!pulse) return false

        const groups = await get_tribe_groups(pulse.id)
        const thinkspeak = groups.find((group) =>
            group.code === THINKSPEAK_GROUP_CODE || group.name === THINKSPEAK_GROUP_NAME
        )
        if (!thinkspeak) return false

        const memberships = await get_memberships(access_token, pulse.id, thinkspeak.id, {
            mine: true,
            status: 'active',
        })

        return memberships.some((membership) => membership.status === 'active')
    } catch {
        return false
    }
}

/**
 * The content.manage gate. Its legacy expression (gate_source legacy and
 * shadow) is the JWT superuser claim or an active Thinkspeak membership.
 */
export async function can_manage_content(gates: GateContext, auth_token: string | false): Promise<boolean> {
    if (!auth_token) return false

    return can_custom(gates, 'content.manage', async () =>
        legacy_superuser(gates) || await is_thinkspeak_member(auth_token)
    )
}
