/**
 * Where a fleet is in its life, as every fleet view shows it:
 * cancelled wins over tracking; a tracked fleet is active until it has an end time.
 */
export type FleetPhase = 'cancelled' | 'active' | 'completed' | 'upcoming'

export interface FleetPhaseFields {
    status?:    string | null;
    tracking?:  { end_time?: Date | string | null } | null;
}

export function fleet_phase(fleet: FleetPhaseFields): FleetPhase {
    if (fleet.status === 'cancelled') return 'cancelled'
    if (!fleet.tracking) return 'upcoming'
    return fleet.tracking.end_time ? 'completed' : 'active'
}
