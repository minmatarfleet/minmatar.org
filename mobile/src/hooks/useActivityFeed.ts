import { useMemo } from 'react';

import { getActivityFeed } from '@/src/data/mockActivity';
import type { ActivityItem } from '@/src/types/activity';

export function useActivityFeed(): ActivityItem[] {
  return useMemo(() => getActivityFeed(), []);
}
