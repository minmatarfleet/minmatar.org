import type { SummaryCharacter, TribeGroup, TribeMembership } from '@dtypes/api.minmatar.org'

export function tribe_group_is_leader(args: {
    group: TribeGroup | null | undefined
    membership: TribeMembership | null
    user_characters?: Pick<SummaryCharacter, 'character_id'>[]
}): boolean {
    const chief_id = args.group?.chief?.character_id
    if (!chief_id) return false
    if (args.membership?.primary_character_id === chief_id) return true
    if (args.membership?.characters?.some((character) => character.character_id === chief_id))
        return true
    return Boolean(args.user_characters?.some((character) => character.character_id === chief_id))
}

export function tribe_group_can_manage(args: {
    group: TribeGroup | null | undefined
    is_leader: boolean
    is_superuser: boolean
}): boolean {
    return Boolean(args.group?.can_manage) || args.is_leader || args.is_superuser
}
