export type FleetTypes = 'strategic' | 'non_strategic' | 'training';

export type TrackingStatus = 'pending' | 'active' | 'complete' | 'cancelled' | 'unknown';

export interface Tracking {
  id: number;
  start_time?: Date;
  end_time?: Date;
  is_registered?: boolean;
}

export interface FleetItem {
  id: number;
  type?: FleetTypes;
  audience: string;
  members_count?: number;
  description?: string;
  objective?: string;
  doctrine_id?: number;
  start_time: Date;
  fleet_commander_id: number;
  fleet_commander_name: string;
  fleet_commander_fleet_count?: number;
  corporation_id?: number;
  corporation_name?: string;
  location?: string;
  tracking?: Tracking;
  status?: TrackingStatus;
  aar_link?: string;
}
