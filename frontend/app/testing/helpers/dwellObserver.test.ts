import { afterEach, describe, expect, it, vi } from 'vitest'

import {
    DWELL_MS,
    VISIBLE_RATIO,
    clearAllDwellTimers,
    clearDwellTimer,
    handleDwellIntersection,
    isSufficientlyVisible,
    scheduleDwell,
    type DwellTimers,
    type VisibilityEntry,
} from '@helpers/pageProgress/dwellObserver'

function entry(overrides: Partial<VisibilityEntry> = {}): VisibilityEntry {
    return {
        isIntersecting: true,
        intersectionRatio: 0.6,
        boundingClientRect: { height: 400 },
        intersectionRect: { height: 240 },
        rootBounds: { height: 800 },
        ...overrides,
    }
}

describe('dwellObserver', () => {
    afterEach(() => {
        vi.useRealTimers()
    })

    it('uses the locked visibility and dwell constants', () => {
        expect(VISIBLE_RATIO).toBe(0.5)
        expect(DWELL_MS).toBe(1000)
    })

    it('treats ratio >= 0.5 as sufficiently visible', () => {
        expect(isSufficientlyVisible(entry({ intersectionRatio: 0.5 }))).toBe(true)
        expect(isSufficientlyVisible(entry({ intersectionRatio: 0.49 }))).toBe(false)
        expect(isSufficientlyVisible(entry({ isIntersecting: false, intersectionRatio: 1 }))).toBe(false)
    })

    it('counts tall sections by viewport coverage', () => {
        expect(
            isSufficientlyVisible(
                entry({
                    intersectionRatio: 0.2,
                    boundingClientRect: { height: 3000 },
                    intersectionRect: { height: 300 },
                    rootBounds: { height: 800 },
                }),
            ),
        ).toBe(false)

        expect(
            isSufficientlyVisible(
                entry({
                    intersectionRatio: 0.2,
                    boundingClientRect: { height: 3000 },
                    intersectionRect: { height: 400 },
                    rootBounds: { height: 800 },
                }),
            ),
        ).toBe(true)
    })

    it('uses viewport fallback when rootBounds is null for tall sections', () => {
        expect(
            isSufficientlyVisible(
                entry({
                    intersectionRatio: 0.2,
                    boundingClientRect: { height: 3000 },
                    intersectionRect: { height: 500 },
                    rootBounds: null,
                }),
                VISIBLE_RATIO,
                800,
            ),
        ).toBe(true)

        expect(
            isSufficientlyVisible(
                entry({
                    intersectionRatio: 0.2,
                    boundingClientRect: { height: 3000 },
                    intersectionRect: { height: 500 },
                    rootBounds: null,
                }),
                VISIBLE_RATIO,
                0,
            ),
        ).toBe(false)
    })

    it('starts dwell once and fires after DWELL_MS', () => {
        vi.useFakeTimers()
        const timers: DwellTimers = {}
        const onComplete = vi.fn()

        expect(scheduleDwell(timers, 'intro', onComplete)).toBe(true)
        expect(scheduleDwell(timers, 'intro', onComplete)).toBe(false)

        vi.advanceTimersByTime(DWELL_MS - 1)
        expect(onComplete).not.toHaveBeenCalled()

        vi.advanceTimersByTime(1)
        expect(onComplete).toHaveBeenCalledOnce()
        expect(onComplete).toHaveBeenCalledWith('intro')
        expect(timers.intro).toBeUndefined()
    })

    it('clears dwell when visibility drops before completion', () => {
        vi.useFakeTimers()
        const timers: DwellTimers = {}
        const onComplete = vi.fn()

        handleDwellIntersection(timers, 'ships', entry({ intersectionRatio: 0.8 }), {
            alreadyRead: false,
            pending: false,
            onDwellComplete: onComplete,
        })
        expect(timers.ships).toBeDefined()

        handleDwellIntersection(timers, 'ships', entry({ intersectionRatio: 0.1 }), {
            alreadyRead: false,
            pending: false,
            onDwellComplete: onComplete,
        })
        expect(timers.ships).toBeUndefined()

        vi.advanceTimersByTime(DWELL_MS)
        expect(onComplete).not.toHaveBeenCalled()
    })

    it('ignores already-read or pending sections', () => {
        const timers: DwellTimers = {}
        const onComplete = vi.fn()

        expect(
            handleDwellIntersection(timers, 'a', entry(), {
                alreadyRead: true,
                pending: false,
                onDwellComplete: onComplete,
            }),
        ).toBe('ignored')

        expect(
            handleDwellIntersection(timers, 'b', entry(), {
                alreadyRead: false,
                pending: true,
                onDwellComplete: onComplete,
            }),
        ).toBe('ignored')

        expect(timers).toEqual({})
    })

    it('clearAllDwellTimers removes every pending timer', () => {
        vi.useFakeTimers()
        const timers: DwellTimers = {}
        const onComplete = vi.fn()
        scheduleDwell(timers, 'a', onComplete)
        scheduleDwell(timers, 'b', onComplete)
        clearDwellTimer(timers, 'missing')
        clearAllDwellTimers(timers)
        vi.advanceTimersByTime(DWELL_MS)
        expect(onComplete).not.toHaveBeenCalled()
        expect(timers).toEqual({})
    })

    it('does not complete dwell for a short TOC-style flash', () => {
        vi.useFakeTimers()
        const timers: DwellTimers = {}
        const onComplete = vi.fn()

        handleDwellIntersection(timers, 'matchups', entry({ intersectionRatio: 0.95 }), {
            alreadyRead: false,
            pending: false,
            onDwellComplete: onComplete,
        })
        vi.advanceTimersByTime(200)
        handleDwellIntersection(
            timers,
            'matchups',
            entry({ isIntersecting: false, intersectionRatio: 0 }),
            {
                alreadyRead: false,
                pending: false,
                onDwellComplete: onComplete,
            },
        )
        vi.advanceTimersByTime(DWELL_MS)
        expect(onComplete).not.toHaveBeenCalled()
    })

    it('completes dwell after sustained visibility', () => {
        vi.useFakeTimers()
        const timers: DwellTimers = {}
        const onComplete = vi.fn()

        handleDwellIntersection(timers, 'credits', entry({ intersectionRatio: 0.8 }), {
            alreadyRead: false,
            pending: false,
            onDwellComplete: onComplete,
        })
        vi.advanceTimersByTime(DWELL_MS)
        expect(onComplete).toHaveBeenCalledWith('credits')
    })
})
