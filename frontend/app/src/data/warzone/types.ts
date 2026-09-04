export type WarzoneMilitiaId = 'minmatar' | 'amarr'

export type WarzoneMilitiaScoreboard = {
    militia: WarzoneMilitiaId
    occupancy_net: number
    systems_held: number
    enlisted_pilots: number
    enlisted_pilots_label: string
    active_pilots: number
    active_pilots_label: string
    kills_last_week: number
    victory_points_last_week: number
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
    dotlan_href: string
    zkill_href: string
}

export type WarzoneTrafficRow = {
    system: string
    system_id?: number
    href: string | null
    front: string
    ships: number
    vs_last_month: number
    isk?: number
    isk_label: string
    holds_today: WarzoneMilitiaId
}

export type WarzoneFrontCard = {
    name: string
    regions: string
    occupancy_label: string
    ships: number
    ships_label: string
    hottest_system: string
    dek: string
}

export type WarzoneFocusLink = {
    href: string
    label: string
}

export type WarzoneEngagementSlice = {
    label: string
    value: number
}

export type WarzonePilot = {
    characterId: number
    name: string
    killmails: number
    /** Alliance name, or corporation name when the pilot has no alliance. */
    affiliation: string
    affiliation_id: number
    affiliation_kind: 'alliance' | 'corporation'
}

export type WarzonePilotBoard = {
    title: string
    minmatar: readonly WarzonePilot[]
    amarr: readonly WarzonePilot[]
}

export type WarzoneShip = {
    typeId: number
    name: string
    count: number
}

export type WarzoneShipBoard = {
    title: string
    ships: readonly WarzoneShip[]
}

export type WarzoneGroup = {
    id: number
    kind: 'alliance' | 'corporation'
    name: string
    killmails: number
    isk_destroyed: number
    ships_lost: number
    militia: WarzoneMilitiaId | null
    /** Display faction: 'Minmatar', 'Amarr', 'Angel Cartel', 'Guristas', or 'Neutral'. */
    faction: string
    /** Dominant militia faction id (500002/500003/500011/500010), or null if none. */
    faction_id: number | null
    /** Share of the group's kills this month that happened in the warzone. */
    fw_share: number
}

export type WarzoneInvolvementStep = {
    title: string
    text: string
    href: string
    label: string
}

export type WarzoneMethodologyEntry = {
    label: string
    text: string
}

export type WarzoneIssue = {
    slug: string
    permalink_path: string
    cover_image: string
    published_at: Date
    period_utc: string
    /** Short name of the month being compared against, e.g. "June". */
    previous_period_label: string
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
        amarr_isk: number
        minmatar_isk: number
        other_ships: number
        other_isk: number
        engagement_mix: readonly WarzoneEngagementSlice[]
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
    pilots: {
        /** Where the boards come from and what they cover. */
        scope: string
        boards: readonly WarzonePilotBoard[]
    }
    top_ships: {
        boards: readonly WarzoneShipBoard[]
    }
    groups: {
        scope: string
        rows: readonly WarzoneGroup[]
    }
    get_involved: {
        steps: readonly WarzoneInvolvementStep[]
        actions: readonly WarzoneFocusLink[]
        /** Guide slugs from the learning catalog, in display order. */
        featured_guides: readonly string[]
    }
    methodology: readonly WarzoneMethodologyEntry[]
}
