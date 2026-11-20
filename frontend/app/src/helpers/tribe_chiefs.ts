import type { Tribe, TribeGroup } from '@dtypes/api.minmatar.org'
import type { TribeChiefOpenSeat } from '@dtypes/layout_components'

/** A group's empty timezone seats (US, EU, AU order). */
export function open_chief_seats(group: TribeGroup | null): TribeChiefOpenSeat[] {
    // Older backends send no seats: treat the group as one seat.
    return (group?.chiefs ?? [])
        .filter((seat) => seat.is_open)
        .map((seat) => ({ region: seat.region, label: seat.label }))
}

/** The group's seated chiefs with their timezone (hidden rosters send none). */
export function seated_chiefs(group: TribeGroup | null | undefined) {
    if (!group || group.chief_is_interim) return []
    return (group.chiefs ?? []).flatMap((seat) => seat.chief ? [{ chief: seat.chief, label: seat.label }] : [])
}

/** Help wanted shows for a seat with no chief, or a group with an open timezone seat. */
export function needs_chief(group: TribeGroup | null, tribe: Tribe | null = null): boolean {
    const seat = group ?? tribe
    if (!seat) return false
    if (seat.chief_is_interim) return true
    return group !== null && open_chief_seats(group).length > 0
}

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
        open_seats: open_chief_seats(group),
        partly_filled: group !== null && !group.chief_is_interim,
    }
}
