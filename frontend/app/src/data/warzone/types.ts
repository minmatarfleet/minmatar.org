export type WarzoneMilitiaId = 'minmatar' | 'amarr'

export type WarzoneMilitiaScoreboard = {
    militia: WarzoneMilitiaId
    occupancy_net: number
    systems_held: number
    enlisted_pilots_label: string
    kills_last_week: number
    victory_points_last_week_label: string
}

export type WarzoneFightPin = {
    system: string
    date_label: string
    dek: string
    ships: number
    isk_label: string
    vs_last_month: number
    links: readonly { href: string; label: string }[]
}

export type WarzoneOccupancyChange = {
    date_label: string
    system: string
    taken_by: WarzoneMilitiaId
    ships: number
    vs_last_month: number
    isk_label: string
    holds_today: WarzoneMilitiaId
    note: string
    dotlan_href: string
    zkill_href: string
}

export type WarzoneTrafficRow = {
    system: string
    href: string | null
    front: string
    ships: number
    vs_last_month: number
    isk_label: string
    holds_today: WarzoneMilitiaId
}

export type WarzoneFrontCard = {
    name: string
    occupancy_label: string
    ships_label: string
    hottest_system: string
    dek: string
}

export type WarzoneFocusLink = {
    href: string
    label: string
}

export type WarzoneIssue = {
    slug: string
    permalink_path: string
    cover_image: string
    published_at: Date
    period_utc: string
    esi_as_of: string
    who_won: string
    opening: string
    sampled_ships: number
    sampled_isk: number
    focus_name: string
    occupancy_changes: number
    occupancy_net_amarr: number
    systems_that_moved: number
    occupancy_dek: string
    scoreboard: readonly WarzoneMilitiaScoreboard[]
    fights: readonly WarzoneFightPin[]
    occupancy: readonly WarzoneOccupancyChange[]
    traffic: readonly WarzoneTrafficRow[]
    traffic_footnote: string
    fronts: readonly WarzoneFrontCard[]
    focus: {
        title: string
        window_label: string
        dek: readonly string[]
        ships: number
        isk: number
        unique_pilots: number
        flip_label: string
        minmatar_pilots: number
        minmatar_ships: number
        amarr_pilots: number
        amarr_ships: number
        small_gang_kills: number
        closing: string
        links: readonly WarzoneFocusLink[]
        campaign_path: string
    }
    fleet: {
        tracked_fleets: number
        untracked_forms_lower_bound: number
        largest_public_pickup: number
        dek: string
    }
    how_to_fly: string
    how_to_fly_links: readonly WarzoneFocusLink[]
    cannot_see: string
    methodology: string
}
