import { useMemo } from 'react';

import { getWarzoneBriefing } from '@/src/data/mockWarzone';
import type { WarzoneBriefing } from '@/src/types/warzone';

export function useWarzoneBriefing(): WarzoneBriefing {
  return useMemo(() => getWarzoneBriefing(), []);
}
