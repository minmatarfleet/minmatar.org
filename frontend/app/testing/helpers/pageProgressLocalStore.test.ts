import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
    LOCAL_STORE_KEY,
    ackPageLocal,
    clearAll,
    clearPage,
    loadPage,
    markSectionLocal,
    progressPercent,
    takePendingForImport,
} from '@helpers/pageProgress/localStore'

describe('pageProgress localStore', () => {
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

    it('marks sections and computes percent', () => {
        const entry = markSectionLocal({
            page_key: 'alliance/values',
            version: 'v1',
            page_title: 'Values',
            section_total: 4,
            section_id: 'intro',
        })
        expect(entry.read_sections).toEqual(['intro'])
        expect(progressPercent(entry.read_sections.length, entry.section_total)).toBe(25)

        markSectionLocal({
            page_key: 'alliance/values',
            version: 'v1',
            page_title: 'Values',
            section_total: 4,
            section_id: 'basics',
        })
        const loaded = loadPage('alliance/values', 'v1')
        expect(loaded?.read_sections.sort()).toEqual(['basics', 'intro'])
    })

    it('discards stale version on load', () => {
        markSectionLocal({
            page_key: 'guides/bookmarks',
            version: 'old',
            page_title: 'Bookmarks',
            section_total: 2,
            section_id: 'a',
        })
        expect(loadPage('guides/bookmarks', 'new')).toBeNull()
        expect(localStorage.getItem(LOCAL_STORE_KEY)).not.toContain('guides/bookmarks')
    })

    it('acks and takePendingForImport snapshots all pages', () => {
        markSectionLocal({
            page_key: 'a',
            version: '1',
            page_title: 'A',
            section_total: 1,
            section_id: 'x',
        })
        ackPageLocal({
            page_key: 'a',
            version: '1',
            page_title: 'A',
            section_ids: ['x'],
        })
        const pending = takePendingForImport()
        expect(pending).toHaveLength(1)
        expect(pending[0].is_acknowledged).toBe(true)
        expect(pending[0].read_sections).toEqual(['x'])
    })

    it('clearPage and clearAll', () => {
        markSectionLocal({
            page_key: 'p',
            version: '1',
            page_title: 'P',
            section_total: 1,
            section_id: 's',
        })
        clearPage('p')
        expect(loadPage('p', '1')).toBeNull()
        markSectionLocal({
            page_key: 'p',
            version: '1',
            page_title: 'P',
            section_total: 1,
            section_id: 's',
        })
        clearAll()
        expect(localStorage.getItem(LOCAL_STORE_KEY)).toBeNull()
    })
})
