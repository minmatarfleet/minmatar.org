import { useMemo } from 'react';

import { getWarzoneBriefing } from '@/src/data/mockWarzone';
import type { WarzoneBriefing, WarzoneSystemHot } from '@/src/types/warzone';

export { useWarzoneBriefing } from '@/src/hooks/useWarzoneBriefing';

/** @deprecated Use useWarzoneBriefing */
export function useWarzoneHotSystems(limit = 5): WarzoneSystemHot[] {
  const briefing = useMemo(() => getWarzoneBriefing(), []);
  const { amarrContested, minmatarContested, hotKills } = briefing;
  return useMemo(() => {
    const seen = new Set<number>();
    const merged: WarzoneSystemHot[] = [];
    for (const system of [hotKills, ...amarrContested, ...minmatarContested]) {
      if (!system || seen.has(system.system_id)) continue;
      seen.add(system.system_id);
      merged.push(system);
      if (merged.length >= limit) break;
    }
    return merged;
  }, [amarrContested, minmatarContested, hotKills, limit]);
}

export type { WarzoneBriefing };
