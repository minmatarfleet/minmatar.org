import type { SummaryCharacter, TribeGroup, TribeMembership } from '@dtypes/api.minmatar.org'

export function tribe_group_is_leader(args: {
    group: TribeGroup | null | undefined
    membership: TribeMembership | null
    user_characters?: Pick<SummaryCharacter, 'character_id'>[]
}): boolean {
    // Every timezone seat's chief leads; an interim chief (the tribe chief,
    // else the executor) leads a chiefless group.
    const chief_ids = new Set<number>(
        (args.group?.chiefs ?? []).flatMap((seat) => seat.chief ? [seat.chief.character_id] : []),
    )
    const first = args.group?.chief?.character_id
        ?? (args.group?.chief_is_interim ? args.group?.acting_chief?.character_id : undefined)
    if (first) chief_ids.add(first)
    if (chief_ids.size === 0) return false
    if (args.membership?.primary_character_id && chief_ids.has(args.membership.primary_character_id)) return true
    if (args.membership?.characters?.some((character) => chief_ids.has(character.character_id)))
        return true
    return Boolean(args.user_characters?.some((character) => chief_ids.has(character.character_id)))
}

/** can_manage comes from the API, which already grants it to superusers. */
export function tribe_group_can_manage(args: {
    group: TribeGroup | null | undefined
    is_leader: boolean
}): boolean {
    return Boolean(args.group?.can_manage) || args.is_leader
}
