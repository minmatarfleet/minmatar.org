import { useCallback, useEffect, useState } from 'react';

import { listFeed } from '@/src/api/feed';
import { mapApiFeedToActivity } from '@/src/api/mappers/feed';
import type { ActivityItem } from '@/src/types/activity';

const FEED_LOAD_ERROR =
  "We couldn't load recent activity. Check your connection and try again.";

export function useActivityFeed(): {
  items: ActivityItem[];
  loading: boolean;
  refreshing: boolean;
  refresh: () => Promise<void>;
  error: string | null;
} {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const response = await listFeed({ limit: 30, days: 7 });
      const mapped = mapApiFeedToActivity(response.items ?? []);
      setItems(mapped);
    } catch {
      setItems([]);
      setError(FEED_LOAD_ERROR);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { items, loading, refreshing, refresh, error };
}
