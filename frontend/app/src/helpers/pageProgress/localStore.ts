/** Browser stash for anonymous page progress (merged to server on login). */

export const LOCAL_STORE_KEY = 'minmatar.page_progress.v1'
export const MAX_SECTIONS_PER_PAGE = 200

export type LocalPageProgress = {
    version: string
    page_title: string
    section_total: number
    read_sections: string[]
    is_acknowledged: boolean
    updated_at: string
}

export type LocalPageProgressStore = Record<string, LocalPageProgress>

export type LocalPageProgressImport = {
    page_key: string
    version: string
    page_title: string
    section_total: number
    read_sections: string[]
    is_acknowledged: boolean
}

function emptyStore(): LocalPageProgressStore {
    return {}
}

function safeParse(raw: string | null): LocalPageProgressStore {
    if (!raw) return emptyStore()
    try {
        const data = JSON.parse(raw)
        if (!data || typeof data !== 'object' || Array.isArray(data)) return emptyStore()
        return data as LocalPageProgressStore
    } catch {
        return emptyStore()
    }
}

function storage(): Storage | null {
    if (typeof localStorage === 'undefined') return null
    return localStorage
}

/** Load the full anonymous progress blob. */
export function loadStore(): LocalPageProgressStore {
    const ls = storage()
    if (!ls) return emptyStore()
    return safeParse(ls.getItem(LOCAL_STORE_KEY))
}

function writeStore(store: LocalPageProgressStore): void {
    const ls = storage()
    if (!ls) return
    try {
        ls.setItem(LOCAL_STORE_KEY, JSON.stringify(store))
    } catch {
        // Quota / private mode — ignore.
    }
}

export function progressPercent(readCount: number, sectionTotal: number): number {
    if (sectionTotal <= 0) return 0
    return Math.round((100 * readCount) / sectionTotal)
}

/**
 * Return progress for a page if present and version matches.
 * Stale versions are discarded.
 */
export function loadPage(
    pageKey: string,
    version: string,
): LocalPageProgress | null {
    const store = loadStore()
    const entry = store[pageKey]
    if (!entry) return null
    if (entry.version !== version) {
        delete store[pageKey]
        writeStore(store)
        return null
    }
    return entry
}

export function markSectionLocal(options: {
    page_key: string
    version: string
    page_title: string
    section_total: number
    section_id: string
}): LocalPageProgress {
    const store = loadStore()
    const existing = store[options.page_key]
    const base: LocalPageProgress =
        existing && existing.version === options.version
            ? existing
            : {
                  version: options.version,
                  page_title: options.page_title,
                  section_total: options.section_total,
                  read_sections: [],
                  is_acknowledged: false,
                  updated_at: new Date().toISOString(),
              }

    const read = new Set(base.read_sections)
    if (options.section_id) read.add(options.section_id)

    const next: LocalPageProgress = {
        version: options.version,
        page_title: options.page_title || base.page_title,
        section_total: Math.max(base.section_total, options.section_total),
        read_sections: [...read].slice(0, MAX_SECTIONS_PER_PAGE),
        is_acknowledged: base.is_acknowledged,
        updated_at: new Date().toISOString(),
    }
    store[options.page_key] = next
    writeStore(store)
    return next
}

export function ackPageLocal(options: {
    page_key: string
    version: string
    page_title: string
    section_ids: string[]
}): LocalPageProgress {
    const store = loadStore()
    const existing = store[options.page_key]
    const read = new Set(existing?.version === options.version ? existing.read_sections : [])
    for (const id of options.section_ids) {
        if (id) read.add(id)
    }
    const next: LocalPageProgress = {
        version: options.version,
        page_title: options.page_title || existing?.page_title || '',
        section_total: Math.max(
            existing?.version === options.version ? existing.section_total : 0,
            options.section_ids.length,
        ),
        read_sections: [...read].slice(0, MAX_SECTIONS_PER_PAGE),
        is_acknowledged: true,
        updated_at: new Date().toISOString(),
    }
    store[options.page_key] = next
    writeStore(store)
    return next
}

/** Snapshot all pages for import, then optionally clear. */
export function takePendingForImport(): LocalPageProgressImport[] {
    const store = loadStore()
    const pages: LocalPageProgressImport[] = []
    for (const [page_key, entry] of Object.entries(store)) {
        if (!entry?.version) continue
        pages.push({
            page_key,
            version: entry.version,
            page_title: entry.page_title || '',
            section_total: entry.section_total || 0,
            read_sections: (entry.read_sections || []).slice(0, MAX_SECTIONS_PER_PAGE),
            is_acknowledged: !!entry.is_acknowledged,
        })
    }
    return pages
}

export function clearPage(pageKey: string): void {
    const store = loadStore()
    if (!(pageKey in store)) return
    delete store[pageKey]
    writeStore(store)
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
