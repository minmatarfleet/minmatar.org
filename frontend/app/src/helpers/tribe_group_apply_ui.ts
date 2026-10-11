import type { TribeGroup, TribeMembership } from '@dtypes/api.minmatar.org'

export type TribeGroupApplyUiState = {
    membership: TribeMembership | null
    is_approved: boolean
    is_pending: boolean
    has_open_membership: boolean
    can_apply: boolean
    blocked_by_trial: boolean
    can_show_apply: boolean
    show_ineligible: boolean
    affiliation_names: string
}

export function tribe_group_affiliation_names(group: TribeGroup): string {
    return (group.allowed_affiliations ?? []).map((affiliation) => affiliation.name).join(', ')
}

export function tribe_group_apply_ui_state(args: {
    group: TribeGroup
    membership: TribeMembership | null
    is_auth: boolean
    is_leader: boolean
    user_on_trial: boolean
}): TribeGroupApplyUiState {
    const { group, membership, is_auth, is_leader, user_on_trial } = args
    const is_approved = membership?.status === 'active'
    const is_pending = membership?.status === 'pending'
    const has_open_membership = is_pending || is_approved
    const can_apply = Boolean(group.can_apply)
    const blocked_by_trial = Boolean(group.require_off_trial) && user_on_trial
    const can_show_apply =
        (!is_auth || (can_apply && !blocked_by_trial))
        && !is_leader
        && !is_pending
        && !is_approved
    const show_ineligible =
        is_auth
        && !can_apply
        && !is_leader
        && !is_pending
        && !is_approved

    return {
        membership,
        is_approved,
        is_pending,
        has_open_membership,
        can_apply,
        blocked_by_trial,
        can_show_apply,
        show_ineligible,
        affiliation_names: tribe_group_affiliation_names(group),
    }
}
