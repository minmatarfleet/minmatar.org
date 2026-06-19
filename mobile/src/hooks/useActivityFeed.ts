import { useCallback, useEffect, useState } from 'react';

import { listFeed } from '@/src/api/feed';
import { mapApiFeedToActivity } from '@/src/api/mappers/feed';
import { getActivityFeed } from '@/src/data/mockActivity';
import type { ActivityItem } from '@/src/types/activity';

export function useActivityFeed(): {
  items: ActivityItem[];
  refreshing: boolean;
  refresh: () => Promise<void>;
  error: string | null;
  /** True when showing mock preview data (API empty or unreachable). */
  isPreview: boolean;
} {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPreview, setIsPreview] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const response = await listFeed({ limit: 30, days: 7 });
      const mapped = mapApiFeedToActivity(response.items ?? []);
      if (mapped.length > 0) {
        setItems(mapped);
        setIsPreview(false);
        return;
      }
      setItems(getActivityFeed());
      setIsPreview(true);
    } catch (err) {
      setItems(getActivityFeed());
      setIsPreview(true);
      setError(
        err instanceof Error
          ? `Live feed unavailable (${err.message}). Showing preview data.`
          : 'Live feed unavailable. Showing preview data.',
      );
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { items, refreshing, refresh, error, isPreview };
}
