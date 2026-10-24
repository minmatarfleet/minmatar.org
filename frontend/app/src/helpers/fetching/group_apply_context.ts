import type {
    SummaryCharacter,
    TribeAvailableCharacter,
    TribeGroup,
    TribeMembership,
} from '@dtypes/api.minmatar.org'
import { get_membership_characters_available, get_memberships, get_tribe_group } from '@helpers/api.minmatar.org/tribes'
import { get_characters_summary_sorted } from '@helpers/fetching/characters'
import { get_user_profile } from '@helpers/permissions'
import { tribe_group_is_leader } from '@helpers/tribe_group_viewer'

export interface GroupApplyContext {
    group: TribeGroup;
    user_characters: SummaryCharacter[];
    available_characters: TribeAvailableCharacter[];
    membership_by_group: Map<number, TribeMembership | null>;
    is_leader: boolean;
    user_on_trial: boolean;
}

/**
 * What `TribeGroupApplyHint` needs to offer "apply" on a members-only gate.
 * Null when the group can't be read; the gate then shows without the button.
 */
export async function get_group_apply_context(args: {
    access_token?: string | false | null;
    username?: string | null;
    tribe_id: number;
    group_id: number;
}): Promise<GroupApplyContext | null> {
    const { access_token, username, tribe_id, group_id } = args

    try {
        const group = await get_tribe_group(tribe_id, group_id, access_token)
        const membership_by_group = new Map<number, TribeMembership | null>()
        let user_characters: SummaryCharacter[] = []
        let available_characters: TribeAvailableCharacter[] = []
        let user_on_trial = false

        if (access_token) {
            const [summary, memberships, available, profile] = await Promise.all([
                get_characters_summary_sorted(access_token),
                get_memberships(access_token, tribe_id, group_id, { mine: true }).catch(() => []),
                get_membership_characters_available(access_token, tribe_id, group_id).catch(() => []),
                username ? get_user_profile(username) : Promise.resolve(null),
            ])
            user_characters = summary.characters ?? []
            membership_by_group.set(group_id, memberships[0] ?? null)
            available_characters = available
            user_on_trial = profile?.community_status === 'trial'
        }

        return {
            group,
            user_characters,
            available_characters,
            membership_by_group,
            is_leader: tribe_group_is_leader({
                group,
                membership: membership_by_group.get(group_id) ?? null,
                user_characters,
            }),
            user_on_trial,
        }
    } catch {
        return null
    }
}
