import type { ApiWarzoneBriefingResponse, ApiWarzoneSystem } from '@/src/api/types/warzone';
import type { WarzoneBriefing, WarzoneSystemHot } from '@/src/types/warzone';

function mapSystem(row: ApiWarzoneSystem): WarzoneSystemHot {
  return {
    system_id: row.system_id,
    system_name: row.system_name,
    sun_type_id: row.sun_type_id,
    contested_percent: row.contested_percent,
    delta_24h: row.delta_24h,
    kills_24h: row.kills_24h,
    front: row.front,
    occupier: row.occupier ?? undefined,
  };
}

export function mapApiWarzoneBriefing(response: ApiWarzoneBriefingResponse): WarzoneBriefing {
  return {
    hotKills: response.hot_kills ? mapSystem(response.hot_kills) : null,
    amarrContested: response.amarr_contested.map(mapSystem),
    minmatarContested: response.minmatar_contested.map(mapSystem),
    changes24h: response.changes_24h.map(mapSystem),
    updatedAt: response.updated_at ?? undefined,
    hasFull24hWindow: response.has_full_24h_window,
  };
}

export const EMPTY_WARZONE_BRIEFING: WarzoneBriefing = {
  hotKills: null,
  amarrContested: [],
  minmatarContested: [],
  changes24h: [],
};
