export type WarzoneFront = 'amarr' | 'minmatar';

export interface WarzoneSystemHot {
  system_id: number;
  system_name: string;
  /** Star type ID — used for distinct system art via images.evetech.net. */
  sun_type_id: number;
  contested_percent: number;
  delta_24h: number;
  kills_24h: number;
  front: WarzoneFront;
  occupier?: 'minmatar' | 'amarr' | 'contested';
}

export interface WarzoneBriefing {
  amarrContested: WarzoneSystemHot[];
  minmatarContested: WarzoneSystemHot[];
  hotKills: WarzoneSystemHot | null;
  changes24h: WarzoneSystemHot[];
  updatedAt?: string;
  hasFull24hWindow?: boolean;
}
