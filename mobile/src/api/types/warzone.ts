import type { WarzoneFront } from '@/src/types/warzone';

export interface ApiWarzoneSystem {
  system_id: number;
  system_name: string;
  sun_type_id: number;
  contested_percent: number;
  delta_24h: number;
  kills_24h: number;
  front: WarzoneFront;
  occupier: 'minmatar' | 'amarr' | 'contested' | null;
}

export interface ApiWarzoneBriefingResponse {
  hot_kills: ApiWarzoneSystem | null;
  amarr_contested: ApiWarzoneSystem[];
  minmatar_contested: ApiWarzoneSystem[];
  changes_24h: ApiWarzoneSystem[];
  updated_at: string | null;
  has_full_24h_window: boolean;
}
