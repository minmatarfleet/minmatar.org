/**
 * The FC as fleet rows name them: their main, and "as {alt}" when they run
 * the fleet in game on another character (docs/fleets/fleet-on-alt.md).
 */
export interface FleetCommanderNames {
    fleet_commander_name:       string;
    fleet_commander_alt_name?:  string | null;
}

export function fleet_commander_label(fleet: FleetCommanderNames, as_word: string): string {
    if (!fleet.fleet_commander_alt_name)
        return fleet.fleet_commander_name
    return `${fleet.fleet_commander_name} ${as_word} ${fleet.fleet_commander_alt_name}`
}
