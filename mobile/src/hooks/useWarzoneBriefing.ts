import { useCallback, useEffect, useState } from 'react';

import { EMPTY_WARZONE_BRIEFING, mapApiWarzoneBriefing } from '@/src/api/mappers/warzone';
import { getWarzoneBriefing } from '@/src/api/warzone';
import type { WarzoneBriefing } from '@/src/types/warzone';

export function useWarzoneBriefing(): {
  briefing: WarzoneBriefing;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [briefing, setBriefing] = useState<WarzoneBriefing>(EMPTY_WARZONE_BRIEFING);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const response = await getWarzoneBriefing();
      setBriefing(mapApiWarzoneBriefing(response));
    } catch {
      setBriefing(EMPTY_WARZONE_BRIEFING);
      setError("We couldn't load warzone data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { briefing, loading, error, refresh };
}
