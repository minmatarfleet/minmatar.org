export type ActivityFaction = 'amarr' | 'minmatar' | 'pirate';

export type ActivityKind =
  | 'fleet_active'
  | 'killmail_batch'
  | 'communication'
  | 'militia_joins';

export interface ActivityPilot {
  character_id: number;
  name: string;
}

export interface ActivityShip {
  name: string;
  count: number;
}

export interface ActivityItem {
  id: string;
  kind: ActivityKind;
  timestamp: Date;
  /** Server-rendered copy when available */
  title?: string;
  subheader?: string;
  summary?: string;
  /** fleet_active */
  faction?: ActivityFaction;
  system?: string;
  kills?: number;
  pilots?: number;
  composition?: string;
  roster?: ActivityPilot[];
  roster_total?: number;
  /** killmail_batch */
  killmail_count?: number;
  window_minutes?: number;
  ships?: ActivityShip[];
  /** communication */
  author?: string;
  message?: string;
  /** militia_joins */
  join_count?: number;
}
