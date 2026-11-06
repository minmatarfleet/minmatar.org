import type { Tribe, TribeGroup } from '@dtypes/api.minmatar.org'

/** Who stands in for an open seat, for TribeChiefHelpWanted (docs/tribes/interim-chiefs.md). */
export function help_wanted_props(tribe: Tribe, group: TribeGroup | null = null) {
    const seat = group ?? tribe
    return {
        tribe_id: tribe.id,
        group_id: group?.id ?? null,
        seat_name: seat.name,
        tribe_name: tribe.name,
        interim_name: seat.acting_chief?.character_name ?? null,
        // A group's stand-in is its tribe chief unless the tribe has none.
        interim_is_executor: !tribe.chief,
        has_volunteered: seat.has_volunteered,
        can_appoint: seat.can_appoint_chief,
    }
}
