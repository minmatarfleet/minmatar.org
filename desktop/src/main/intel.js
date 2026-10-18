// Intel window data: the shared intel sheet (pilot d-scan / Local reports) and the feed's capital
// and Amarr fleet pings, plus the paste -> preview -> share flow and the report detail view.
// Main process only; windows get view() through the normal state push. main.js polls refresh() every
// REFRESH_MS while the Intel window is up (poller.js).
const { IntelMap } = require('./intel_map')
const { is_unauthorized } = require('./api')

const REFRESH_MS = 30_000
const NEW_FOR_MS = 5 * 60_000   // a row counts as new this long after it first shows up
const MAX_PASTE_CHARS = 200_000  // same cap as the API
const DEFAULT_RANGE = 5          // jumps, until the pilot picks another (saved in window.intel.range)

class IntelController {
    constructor({ api, web_url, on_change, on_unauthorized = () => {}, diag = () => {}, now = () => Date.now() }) {
        this.api = api
        this.web_url = web_url
        this.on_change = on_change
        this.on_unauthorized = on_unauthorized
        this.diag = diag
        this.now = now
        this.map = new IntelMap()
        this.map_loading = null
        this.reset()
    }

    reset() {
        this.raw_items = []
        this.items = []
        this.first_seen = new Map()   // item id -> ms it first appeared
        this.loaded_once = false
        this.loading = false
        this.error = null
        this.updated_at = null
        this.origin = null            // { character, system } of the client in front
        this.range = DEFAULT_RANGE    // jumps; null = any distance
        this.draft = null
        this.draft_text = null        // the paste stays here, never in the pushed state
        this.detail = null
    }

    sign_out() {
        this.reset()
    }

    view() {
        return {
            items: this.items,
            loading: this.loading,
            error: this.error,
            updated_at: this.updated_at,
            origin: this.origin,
            range: this.range,
            map_ready: this.map.loaded,
            draft: this.draft,
            detail: this.detail,
        }
    }

    changed() {
        this.on_change(this.view())
    }

    set_options({ range }) {
        if (range !== undefined) this.range = range === null ? null : Math.max(0, Number(range) || 0)
        this.changed()
    }

    set_origin(origin) {
        if (JSON.stringify(origin) === JSON.stringify(this.origin)) return
        this.origin = origin
        if (this.draft && !this.draft.system_edited) this.draft = { ...this.draft, system: origin ? origin.system : '' }
        this.annotate()
        this.changed()
    }

    // ---------------------------------------------------------------- recent list

    async load_map() {
        if (this.map.loaded) return
        if (!this.map_loading) {
            this.map_loading = this.api.intel_map()
                .then(data => this.map.set(data))
                .catch(err => this.diag({ t: 'intel-map-error', message: err.message }))
                .finally(() => { this.map_loading = null })
        }
        await this.map_loading
    }

    annotate() {
        const system = this.origin && this.origin.system
        const now = this.now()
        this.items = this.raw_items.map(item => ({
            ...item,
            jumps: this.map.jumps(system, item.system_id),
            is_new: this.loaded_once && now - (this.first_seen.get(item.id) || 0) < NEW_FOR_MS,
        }))
    }

    // Resolves true when the list loaded, false when it didn't (the poller backs off).
    async refresh() {
        this.loading = true
        this.changed()
        try {
            const [recent] = await Promise.all([this.api.intel_recent(), this.load_map()])
            const now = this.now()
            for (const item of recent.items) {
                if (!this.first_seen.has(item.id)) this.first_seen.set(item.id, this.loaded_once ? now : 0)
            }
            this.raw_items = recent.items
            this.annotate()
            this.loaded_once = true
            this.error = null
            this.updated_at = new Date(now).toISOString()
            return true
        } catch (err) {
            this.diag({ t: 'intel-refresh-error', status: err.status, message: err.message })
            if (is_unauthorized(err)) { this.on_unauthorized(); return false }
            this.error = err.status === 403 ? 'Your account does not have access to intel.' : 'Could not reach Minmatar Fleet. Retrying…'
            return false
        } finally {
            this.loading = false
            this.changed()
        }
    }

    // ---------------------------------------------------------------- paste -> share

    async paste(text, kind = null) {
        text = typeof text === 'string' ? text : ''
        if (!text.trim()) {
            this.draft = { status: 'error', error: 'The clipboard is empty. Copy a d-scan or Local first.' }
            return this.changed()
        }
        if (text.length > MAX_PASTE_CHARS) {
            this.draft = { status: 'error', error: 'That paste is too long.' }
            return this.changed()
        }
        this.draft_text = text
        const keep = this.draft && this.draft.status !== 'error' ? this.draft : {}
        this.draft = {
            status: 'loading',
            kind,
            system: keep.system_edited ? keep.system : (this.origin ? this.origin.system : ''),
            system_edited: !!keep.system_edited,
            note: keep.note || '',
            character: this.origin ? this.origin.character : null,
        }
        this.changed()
        try {
            const preview = await this.api.intel_preview(text, kind)
            if (this.draft_text !== text) return   // pasted again meanwhile
            this.draft = { ...this.draft, status: 'ready', kind: preview.kind, lines: preview.lines, summary: preview.summary }
        } catch (err) {
            if (is_unauthorized(err)) return this.on_unauthorized()
            this.draft = { ...this.draft, status: 'error', error: err.detail || 'Could not read that paste.' }
        }
        this.changed()
    }

    set_kind(kind) {
        if (this.draft_text && ['dscan', 'local'].includes(kind)) return this.paste(this.draft_text, kind)
    }

    edit_draft({ system, note }) {
        if (!this.draft) return
        // Share sends the field back unchanged; only a real change stops it following the client's system.
        if (typeof system === 'string' && system.slice(0, 64) !== this.draft.system) this.draft = { ...this.draft, system: system.slice(0, 64), system_edited: true }
        if (typeof note === 'string') this.draft = { ...this.draft, note: note.slice(0, 200) }
    }

    // Returns the share link (main copies it), or null.
    async share() {
        const draft = this.draft
        if (!draft || draft.status !== 'ready' || !this.draft_text) return null
        this.draft = { ...draft, status: 'sharing' }
        this.changed()
        try {
            const report = await this.api.intel_share({
                text: this.draft_text,
                kind: draft.kind,
                system: draft.system,
                note: draft.note,
                character_name: draft.character,
            })
            const url = this.report_url(report.report_id)
            this.draft = { ...draft, status: 'shared', report_id: report.report_id, url }
            this.draft_text = null
            this.refresh()
            return url
        } catch (err) {
            if (is_unauthorized(err)) { this.on_unauthorized(); return null }
            this.draft = { ...draft, status: 'ready', error: err.detail || 'Could not share. Try again.' }
            this.changed()
            return null
        }
    }

    discard() {
        this.draft = null
        this.draft_text = null
        this.changed()
    }

    // ---------------------------------------------------------------- report detail

    report_url(report_id) {
        return `${this.web_url}/intel/scans/${encodeURIComponent(report_id)}`
    }

    async open_report(report_id) {
        if (typeof report_id !== 'string' || !report_id) return
        this.detail = { status: 'loading', report_id }
        this.changed()
        try {
            const report = await this.api.intel_report(report_id)
            if (!this.detail || this.detail.report_id !== report_id) return
            const { raw, ...rest } = report
            this.detail = {
                status: 'ready',
                ...rest,
                raw_preview: raw.split('\n').slice(0, 12).join('\n'),
                raw_lines: raw.split('\n').filter(Boolean).length,
                jumps: this.map.jumps(this.origin && this.origin.system, report.system_id),
                url: this.report_url(report_id),
            }
        } catch (err) {
            if (is_unauthorized(err)) return this.on_unauthorized()
            this.detail = { status: 'error', report_id, error: err.status === 404 ? 'That report is gone.' : 'Could not load the report.' }
        }
        this.changed()
    }

    close_report() {
        this.detail = null
        this.changed()
    }

    // Only links we built from report ids the API gave us.
    url_for(report_id) {
        const known = (this.detail && this.detail.report_id === report_id) ||
            (this.draft && this.draft.report_id === report_id) ||
            this.raw_items.some(item => item.report_id === report_id)
        return known ? this.report_url(report_id) : null
    }
}

module.exports = { IntelController, REFRESH_MS, NEW_FOR_MS, DEFAULT_RANGE }
