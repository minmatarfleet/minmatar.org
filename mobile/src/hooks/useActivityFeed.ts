import { useCallback, useEffect, useState } from 'react';

import { listFeed } from '@/src/api/feed';
import { mapApiFeedToActivity } from '@/src/api/mappers/feed';
import type { ActivityItem } from '@/src/types/activity';

export function useActivityFeed(): {
  items: ActivityItem[];
  refreshing: boolean;
  refresh: () => Promise<void>;
  error: string | null;
} {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const response = await listFeed({ limit: 30, days: 7 });
      setItems(mapApiFeedToActivity(response.items));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load activity feed');
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { items, refreshing, refresh, error };
}
