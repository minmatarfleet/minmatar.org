const EVE_TZ = 'UTC';

export function nowInEve(): Date {
  return new Date();
}

export function isSameEveDay(a: Date, b: Date): boolean {
  const opts: Intl.DateTimeFormatOptions = { timeZone: EVE_TZ, year: 'numeric', month: '2-digit', day: '2-digit' };
  return a.toLocaleDateString('en-CA', opts) === b.toLocaleDateString('en-CA', opts);
}

export function getEveWeekdayShort(date: Date): string {
  return date.toLocaleDateString('en-US', { timeZone: EVE_TZ, weekday: 'short' });
}

export function isEveWeekend(date: Date): boolean {
  const day = getEveWeekdayShort(date);
  return day === 'Fri' || day === 'Sat' || day === 'Sun';
}

export function formatEveTimeShort(date: Date): string {
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: EVE_TZ,
  });
}

export function formatRelativeDate(date: Date): string {
  const diffMs = Date.now() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: EVE_TZ });
}

/** Compact relative stamp for activity timeline rows. */
export function formatTimelineTime(date: Date): string {
  const diffMs = Math.max(0, Date.now() - date.getTime());
  const diffMin = Math.floor(diffMs / (1000 * 60));
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return formatEveTimeShort(date);
}
