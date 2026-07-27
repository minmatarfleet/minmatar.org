/** Browser stash for anonymous Learning Center progress (merged on login). */

import type { LearningPersona } from '@dtypes/api.minmatar.org'

export const LOCAL_STORE_KEY = 'minmatar.learning.v1'
export const PERSONA_COOKIE = 'learning_persona'

export type LearningLocalStore = {
    persona?: LearningPersona
    completed: string[]
    /** True after user confirms the first-open “opens in a new tab” tip. */
    open_new_tab_tip_seen?: boolean
    updated_at?: string
}

function emptyStore(): LearningLocalStore {
    return { completed: [] }
}

function safeParse(raw: string | null): LearningLocalStore {
    if (!raw) return emptyStore()
    try {
        const data = JSON.parse(raw)
        if (!data || typeof data !== 'object' || Array.isArray(data)) return emptyStore()
        const completed = Array.isArray(data.completed)
            ? data.completed.filter((s: unknown) => typeof s === 'string')
            : []
        const persona =
            data.persona === 'alliance' || data.persona === 'militia' || data.persona === 'other'
                ? data.persona
                : undefined
        const open_new_tab_tip_seen = data.open_new_tab_tip_seen === true
        return { persona, completed, open_new_tab_tip_seen, updated_at: data.updated_at }
    } catch {
        return emptyStore()
    }
}

function storage(): Storage | null {
    if (typeof localStorage === 'undefined') return null
    return localStorage
}

export function loadStore(): LearningLocalStore {
    const ls = storage()
    if (!ls) return emptyStore()
    return safeParse(ls.getItem(LOCAL_STORE_KEY))
}

function writeStore(store: LearningLocalStore): void {
    const ls = storage()
    if (!ls) return
    try {
        ls.setItem(
            LOCAL_STORE_KEY,
            JSON.stringify({
                ...store,
                updated_at: new Date().toISOString(),
            }),
        )
    } catch {
        // Quota / private mode — ignore.
    }
}

export function getLocalPersona(): LearningPersona | null {
    return loadStore().persona ?? null
}

export function setLocalPersona(persona: LearningPersona): void {
    const store = loadStore()
    store.persona = persona
    writeStore(store)
}

export function getCompletedSlugs(): string[] {
    return [...loadStore().completed]
}

export function isLearningComplete(slug: string): boolean {
    return loadStore().completed.includes(slug)
}

export function markLearningCompleteLocal(slug: string): void {
    const store = loadStore()
    if (!store.completed.includes(slug)) {
        store.completed.push(slug)
        writeStore(store)
    }
}

export function hasSeenOpenNewTabTip(): boolean {
    return loadStore().open_new_tab_tip_seen === true
}

/** Mark the Open tip as seen only after the user confirms (Open). */
export function markOpenNewTabTipSeen(): void {
    const store = loadStore()
    if (store.open_new_tab_tip_seen) return
    store.open_new_tab_tip_seen = true
    writeStore(store)
}

export type OpenLearningWithTipResult = 'opened_direct' | 'opened_after_tip' | 'dismissed'

/**
 * First Open shows a tip and only opens the URL after OK.
 * After the tip is marked seen, Open goes straight to a new tab.
 *
 * When `tipNavigates` is true, the tip’s accept control is expected to open the
 * URL itself (e.g. `<a target="_blank">`) under the confirm click’s user gesture.
 * Calling `window.open` after `await showTip()` is blocked on many mobile browsers.
 */
export async function openLearningWithNewTabTip(options: {
    url: string
    hasSeenTip: boolean
    markTipSeen: () => void
    showTip: () => Promise<boolean>
    openUrl: (url: string) => void
    /** Tip OK already navigates (real link). Skip post-await window.open. */
    tipNavigates?: boolean
}): Promise<OpenLearningWithTipResult> {
    if (options.hasSeenTip) {
        options.openUrl(options.url)
        return 'opened_direct'
    }
    const accepted = await options.showTip()
    if (!accepted) return 'dismissed'
    options.markTipSeen()
    if (!options.tipNavigates) {
        options.openUrl(options.url)
    }
    return 'opened_after_tip'
}

export function takePendingForImport(): {
    completed_learning_slugs: string[]
    persona: LearningPersona | null
} {
    const store = loadStore()
    return {
        completed_learning_slugs: [...store.completed],
        persona: store.persona ?? null,
    }
}

/** Clear completed learnings after successful server import; keep persona + tip flag. */
export function clearCompletedAfterImport(): void {
    const store = loadStore()
    store.completed = []
    writeStore(store)
}

export type LearningImportServerResult = {
    completed_learning_slugs: string[]
    persona: LearningPersona | null
    imported_slugs?: string[]
}

/**
 * POST local pending progress to the Learning Center import API.
 * On success clears completed slugs via clearCompletedAfterImport (preserves tip + persona).
 */
export async function importPendingToServer(
    apiBase: string,
    authToken: string,
    pending: {
        completed_learning_slugs: string[]
        persona: LearningPersona | null
    },
): Promise<LearningImportServerResult | null> {
    const response = await fetch(`${apiBase}/import`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
            completed_learning_slugs: pending.completed_learning_slugs,
            persona: pending.persona,
        }),
    })
    if (!response.ok) return null
    const data = (await response.json()) as LearningImportServerResult
    clearCompletedAfterImport()
    return data
}

export function clearAll(): void {
    const ls = storage()
    if (!ls) return
    try {
        ls.removeItem(LOCAL_STORE_KEY)
    } catch {
        // ignore
    }
}

export function certificateProgressPercent(
    learningSlugs: string[],
    completed: Set<string> | string[],
): number {
    if (learningSlugs.length <= 0) return 0
    const done = completed instanceof Set ? completed : new Set(completed)
    const read = learningSlugs.filter((slug) => done.has(slug)).length
    return Math.round((100 * read) / learningSlugs.length)
}

export function isExternalLearningUrl(url: string): boolean {
    return /^https?:\/\//i.test(url)
}
