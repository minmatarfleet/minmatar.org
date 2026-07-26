/** Industry-style dwell: section counts as read after sustained visibility. */
export const VISIBLE_RATIO = 0.5
export const DWELL_MS = 1000

export type DwellTimers = Record<string, ReturnType<typeof setTimeout>>

export type VisibilityEntry = {
    isIntersecting: boolean
    intersectionRatio: number
    boundingClientRect: { height: number }
    intersectionRect: { height: number }
    rootBounds: { height: number } | null
}

/**
 * True when enough of the section is on screen.
 * Tall sections (taller than the viewport) never reach intersectionRatio 0.5;
 * for those we require that the section covers at least `visibleRatio` of the
 * viewport height. `fallbackRootHeight` covers browsers/cases where rootBounds
 * is null (implicit viewport).
 */
export function isSufficientlyVisible(
    entry: VisibilityEntry,
    visibleRatio: number = VISIBLE_RATIO,
    fallbackRootHeight: number = 0,
): boolean {
    if (!entry.isIntersecting) return false
    if (entry.intersectionRatio >= visibleRatio) return true

    const rootHeight = entry.rootBounds?.height || fallbackRootHeight
    if (rootHeight <= 0) return false

    return (
        entry.boundingClientRect.height > rootHeight &&
        entry.intersectionRect.height >= rootHeight * visibleRatio
    )
}

/** Manual viewport check used when a dwell timer fires. */
export function isElementSufficientlyVisible(
    el: Element,
    visibleRatio: number = VISIBLE_RATIO,
    viewportHeight: number = 0,
): boolean {
    const rootHeight = viewportHeight || (typeof window !== 'undefined' ? window.innerHeight : 0)
    if (rootHeight <= 0) return false

    const rect = el.getBoundingClientRect()
    const visibleTop = Math.max(rect.top, 0)
    const visibleBottom = Math.min(rect.bottom, rootHeight)
    const visibleHeight = Math.max(0, visibleBottom - visibleTop)
    if (visibleHeight <= 0) return false

    const ratioOfElement = visibleHeight / Math.max(rect.height, 1)
    if (ratioOfElement >= visibleRatio) return true

    // Tall section: enough of the viewport is covered by this element.
    return rect.height > rootHeight && visibleHeight >= rootHeight * visibleRatio
}

export function clearDwellTimer(timers: DwellTimers, sectionId: string): void {
    const timer = timers[sectionId]
    if (timer === undefined) return
    clearTimeout(timer)
    delete timers[sectionId]
}

export function clearAllDwellTimers(timers: DwellTimers): void {
    for (const sectionId of Object.keys(timers)) {
        clearDwellTimer(timers, sectionId)
    }
}

/**
 * Start a dwell timer if one is not already running for this section.
 * Does not restart an in-progress dwell (continuous visibility must accumulate).
 */
export function scheduleDwell(
    timers: DwellTimers,
    sectionId: string,
    onComplete: (sectionId: string) => void,
    dwellMs: number = DWELL_MS,
): boolean {
    if (timers[sectionId] !== undefined) return false
    timers[sectionId] = setTimeout(() => {
        delete timers[sectionId]
        onComplete(sectionId)
    }, dwellMs)
    return true
}

export type DwellHandleResult = 'started' | 'cleared' | 'ignored' | 'unchanged'

/**
 * Apply one intersection update to dwell timers.
 * - sufficiently visible + not read/pending → start dwell once
 * - no longer sufficiently visible → clear dwell
 */
export function handleDwellIntersection(
    timers: DwellTimers,
    sectionId: string,
    entry: VisibilityEntry,
    options: {
        alreadyRead: boolean
        pending: boolean
        onDwellComplete: (sectionId: string) => void
        visibleRatio?: number
        dwellMs?: number
        fallbackRootHeight?: number
    },
): DwellHandleResult {
    if (options.alreadyRead || options.pending) {
        clearDwellTimer(timers, sectionId)
        return 'ignored'
    }

    if (
        isSufficientlyVisible(
            entry,
            options.visibleRatio ?? VISIBLE_RATIO,
            options.fallbackRootHeight ?? 0,
        )
    ) {
        const started = scheduleDwell(
            timers,
            sectionId,
            options.onDwellComplete,
            options.dwellMs ?? DWELL_MS,
        )
        return started ? 'started' : 'unchanged'
    }

    if (timers[sectionId] !== undefined) {
        clearDwellTimer(timers, sectionId)
        return 'cleared'
    }
    return 'unchanged'
}
