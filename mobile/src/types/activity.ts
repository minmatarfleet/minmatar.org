export type ActivityFaction = 'amarr' | 'minmatar' | 'pirate';

export type ActivityKind =
  | 'fleet_active'
  | 'killmail_batch'
  | 'communication'
  | 'militia_joins';

export interface ActivityItem {
  id: string;
  kind: ActivityKind;
  timestamp: Date;
  /** fleet_active */
  faction?: ActivityFaction;
  system?: string;
  kills?: number;
  pilots?: number;
  composition?: string;
  /** killmail_batch */
  killmail_count?: number;
  window_minutes?: number;
  /** communication */
  author?: string;
  title?: string;
  message?: string;
  /** Optional longer copy for modal / preview fallback */
  summary?: string;
  /** militia_joins */
  join_count?: number;
}
