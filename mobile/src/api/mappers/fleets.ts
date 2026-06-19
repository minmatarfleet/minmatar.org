import type { ApiFleet, ApiFleetTracking } from '@/src/api/types';
import type { FleetItem, Tracking, TrackingStatus } from '@/src/types/fleets';

function mapTracking(tracking?: ApiFleetTracking | null): Tracking | undefined {
  if (!tracking) return undefined;
  return {
    id: tracking.id,
    start_time: new Date(tracking.start_time),
    end_time: tracking.end_time ? new Date(tracking.end_time) : undefined,
    is_registered: tracking.is_registered,
  };
}

function mapStatus(fleet: ApiFleet): TrackingStatus {
  if (fleet.status === 'cancelled') return 'cancelled';
  if (fleet.tracking && !fleet.tracking.end_time) return 'active';
  if (fleet.tracking?.end_time) return 'complete';
  if (fleet.status === 'pending') return 'pending';
  if (fleet.status === 'complete') return 'complete';
  return 'unknown';
}

export function mapApiFleetToItem(
  fleet: ApiFleet,
  commanderName: string,
  commanderCharacterId: number,
): FleetItem {
  return {
    id: fleet.id,
    type: fleet.type,
    audience: fleet.audience,
    description: fleet.description,
    objective: fleet.objective ?? undefined,
    doctrine_id: fleet.doctrine_id ?? undefined,
    start_time: fleet.start_time ? new Date(fleet.start_time) : new Date(),
    fleet_commander_id: commanderCharacterId,
    fleet_commander_name: commanderName,
    location: fleet.location,
    tracking: mapTracking(fleet.tracking),
    status: mapStatus(fleet),
    aar_link: fleet.aar_link ?? undefined,
  };
}

export function isActiveFleet(fleet: FleetItem): boolean {
  return fleet.status !== 'cancelled' && !!fleet.tracking && !fleet.tracking.end_time;
}

export function isUpcomingFleet(fleet: FleetItem): boolean {
  return !isActiveFleet(fleet) && fleet.status === 'pending';
}
