import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
    LOCAL_STORE_KEY,
    certificateProgressPercent,
    clearCompletedAfterImport,
    getCompletedSlugs,
    getLocalPersona,
    hasSeenOpenNewTabTip,
    isExternalLearningUrl,
    markLearningCompleteLocal,
    markOpenNewTabTipSeen,
    openLearningWithNewTabTip,
    setLocalPersona,
    takePendingForImport,
} from '@helpers/learning/localStore'

describe('learning localStore', () => {
    beforeEach(() => {
        const map = new Map<string, string>()
        vi.stubGlobal('localStorage', {
            getItem: (k: string) => map.get(k) ?? null,
            setItem: (k: string, v: string) => {
                map.set(k, v)
            },
            removeItem: (k: string) => {
                map.delete(k)
            },
        })
    })

    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it('stores persona and completions', () => {
        setLocalPersona('militia')
        markLearningCompleteLocal('fw-basics')
        markLearningCompleteLocal('fw-basics')
        markLearningCompleteLocal('fw-plexing')

        expect(getLocalPersona()).toBe('militia')
        expect(getCompletedSlugs()).toEqual(['fw-basics', 'fw-plexing'])
        expect(localStorage.getItem(LOCAL_STORE_KEY)).toContain('militia')
    })

    it('takePendingForImport and clearCompletedAfterImport', () => {
        setLocalPersona('alliance')
        markLearningCompleteLocal('intro')
        const pending = takePendingForImport()
        expect(pending.persona).toBe('alliance')
        expect(pending.completed_learning_slugs).toEqual(['intro'])

        clearCompletedAfterImport()
        expect(getCompletedSlugs()).toEqual([])
        expect(getLocalPersona()).toBe('alliance')
    })

    it('clearCompletedAfterImport preserves open_new_tab_tip_seen', () => {
        setLocalPersona('alliance')
        markLearningCompleteLocal('intro')
        markOpenNewTabTipSeen()
        clearCompletedAfterImport()
        expect(getCompletedSlugs()).toEqual([])
        expect(hasSeenOpenNewTabTip()).toBe(true)
        expect(getLocalPersona()).toBe('alliance')
        expect(localStorage.getItem(LOCAL_STORE_KEY)).toContain('open_new_tab_tip_seen')
    })

    it('certificateProgressPercent and external URL helper', () => {
        expect(certificateProgressPercent(['a', 'b', 'c'], ['a', 'c'])).toBe(67)
        expect(certificateProgressPercent([], [])).toBe(0)
        expect(isExternalLearningUrl('https://wiki.minmatar.org/x')).toBe(true)
        expect(isExternalLearningUrl('/guides/abyssals/')).toBe(false)
    })

    it('open new-tab tip is unseen until marked on confirm', () => {
        expect(hasSeenOpenNewTabTip()).toBe(false)
        markOpenNewTabTipSeen()
        markOpenNewTabTipSeen()
        expect(hasSeenOpenNewTabTip()).toBe(true)
        expect(localStorage.getItem(LOCAL_STORE_KEY)).toContain('open_new_tab_tip_seen')
    })

    it('openLearningWithNewTabTip shows tip first, then opens only on OK', async () => {
        const openUrl = vi.fn()
        const markTipSeen = vi.fn()
        const showTip = vi.fn().mockResolvedValue(true)

        const result = await openLearningWithNewTabTip({
            url: 'https://wiki.minmatar.org/guide',
            hasSeenTip: false,
            markTipSeen,
            showTip,
            openUrl,
        })

        expect(result).toBe('opened_after_tip')
        expect(showTip).toHaveBeenCalledOnce()
        expect(markTipSeen).toHaveBeenCalledOnce()
        expect(openUrl).toHaveBeenCalledWith('https://wiki.minmatar.org/guide')
    })

    it('openLearningWithNewTabTip with tipNavigates skips post-await openUrl', async () => {
        const openUrl = vi.fn()
        const markTipSeen = vi.fn()
        const showTip = vi.fn().mockResolvedValue(true)

        const result = await openLearningWithNewTabTip({
            url: 'https://wiki.minmatar.org/guide',
            hasSeenTip: false,
            markTipSeen,
            showTip,
            openUrl,
            tipNavigates: true,
        })

        expect(result).toBe('opened_after_tip')
        expect(showTip).toHaveBeenCalledOnce()
        expect(markTipSeen).toHaveBeenCalledOnce()
        expect(openUrl).not.toHaveBeenCalled()
    })

    it('openLearningWithNewTabTip dismiss without OK opens nothing and leaves tip unseen', async () => {
        const openUrl = vi.fn()
        const markTipSeen = vi.fn()
        const showTip = vi.fn().mockResolvedValue(false)

        const result = await openLearningWithNewTabTip({
            url: 'https://wiki.minmatar.org/guide',
            hasSeenTip: false,
            markTipSeen,
            showTip,
            openUrl,
        })

        expect(result).toBe('dismissed')
        expect(showTip).toHaveBeenCalledOnce()
        expect(markTipSeen).not.toHaveBeenCalled()
        expect(openUrl).not.toHaveBeenCalled()
    })

    it('openLearningWithNewTabTip skips tip when already seen', async () => {
        const openUrl = vi.fn()
        const markTipSeen = vi.fn()
        const showTip = vi.fn()

        const result = await openLearningWithNewTabTip({
            url: '/guides/abyssals/',
            hasSeenTip: true,
            markTipSeen,
            showTip,
            openUrl,
        })

        expect(result).toBe('opened_direct')
        expect(showTip).not.toHaveBeenCalled()
        expect(markTipSeen).not.toHaveBeenCalled()
        expect(openUrl).toHaveBeenCalledWith('/guides/abyssals/')
    })
})
