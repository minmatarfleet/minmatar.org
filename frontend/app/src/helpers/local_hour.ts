/**
 * The colour and word for a viewer's local hour, on the security-status
 * ramp: sleeptime reds, daytime yellows, evening greens and blues, purple
 * from 23:00. Index = the local hour (0–23).
 */
export type LocalHourWord = 'sleeptime' | 'daytime' | 'nighttime'

export const LOCAL_HOUR_BANDS:ReadonlyArray<readonly [string, LocalHourWord]> = Array.from({ length: 24 }, (_, hour) => {
    if (hour < 7) return ['text-status-point-2', 'sleeptime'] as const
    if (hour < 8) return ['text-status-point-3', 'sleeptime'] as const
    if (hour < 9) return ['text-status-point-4', 'daytime'] as const
    if (hour < 19) return ['text-status-point-5', 'daytime'] as const
    if (hour < 20) return ['text-status-point-6', 'nighttime'] as const
    if (hour < 21) return ['text-status-point-7', 'nighttime'] as const
    if (hour < 22) return ['text-status-point-8', 'nighttime'] as const
    if (hour < 23) return ['text-status-point-9', 'nighttime'] as const
    return ['text-status-null', 'sleeptime'] as const
})

/** The bands with their words translated, for an Alpine `x-data` lookup by hour. */
export const local_hour_bands = (t:(key:LocalHourWord) => string):[string, string][] =>
    LOCAL_HOUR_BANDS.map(([css_class, word]) => [css_class, t(word)])
