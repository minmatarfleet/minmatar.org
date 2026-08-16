import { get_tribes, get_tribe_groups, get_memberships } from '@helpers/api.minmatar.org/tribes'

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
