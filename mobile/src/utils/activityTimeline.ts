import type { ActivityItem } from '@/src/types/activity';
import { nowInEve } from '@/src/utils/eveTime';

export type ActivityTimelineSectionKey =
  | 'past_hour'
  | 'earlier_today'
  | 'yesterday'
  | 'earlier_this_week';

const SECTION_ORDER: ActivityTimelineSectionKey[] = [
  'past_hour',
  'earlier_today',
  'yesterday',
  'earlier_this_week',
];

const SECTION_TITLES: Record<ActivityTimelineSectionKey, string> = {
  past_hour: 'Past hour',
  earlier_today: 'Earlier today',
  yesterday: 'Yesterday',
  earlier_this_week: 'Earlier this week',
};

const ONE_HOUR_MS = 60 * 60 * 1000;
const ONE_DAY_MS = 24 * ONE_HOUR_MS;
const TWO_DAYS_MS = 2 * ONE_DAY_MS;
const SEVEN_DAYS_MS = 7 * ONE_DAY_MS;

/**
 * Rolling hour windows — not EVE/UTC calendar days.
 * "Earlier today" / "Yesterday" follow local elapsed time so USTZ/EUTZ
 * players aren't split at UTC midnight.
 */
export function getActivityTimelineSection(
  timestamp: Date,
  now: Date = nowInEve(),
): ActivityTimelineSectionKey | null {
  const ageMs = now.getTime() - timestamp.getTime();
  if (ageMs < 0 || ageMs >= SEVEN_DAYS_MS) {
    return null;
  }
  if (ageMs < ONE_HOUR_MS) {
    return 'past_hour';
  }
  if (ageMs < ONE_DAY_MS) {
    return 'earlier_today';
  }
  if (ageMs < TWO_DAYS_MS) {
    return 'yesterday';
  }
  return 'earlier_this_week';
}

export interface ActivityTimelineSection {
  key: ActivityTimelineSectionKey;
  title: string;
  data: ActivityItem[];
}

/** Group sorted feed items into non-empty timeline sections (newest first within each). */
export function groupActivityByTimeline(
  items: ActivityItem[],
  now: Date = nowInEve(),
): ActivityTimelineSection[] {
  const buckets = new Map<ActivityTimelineSectionKey, ActivityItem[]>();

  for (const item of items) {
    const section = getActivityTimelineSection(item.timestamp, now);
    if (!section) {
      continue;
    }
    const bucket = buckets.get(section) ?? [];
    bucket.push(item);
    buckets.set(section, bucket);
  }

  return SECTION_ORDER.filter((key) => (buckets.get(key)?.length ?? 0) > 0).map((key) => ({
    key,
    title: SECTION_TITLES[key],
    data: buckets.get(key)!,
  }));
}
