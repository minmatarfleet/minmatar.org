// Jumps between two solar systems, from ESI's public route API (GET /route/{origin}/{destination},
// cached by ESI for 24 h). Gate distances don't change, so every pair is asked once per session;
// names from the log engine are resolved to IDs once each. Follows docs/desktop/ccp-third-party-guidelines.md
// rule 12 (identify the app, pin the API version, never re-ask inside the cache time).
const { ESI, ESI_HEADERS, universe_ids, find_named } = require('./esi')

const MAX_PAIRS = 500

class RouteFinder {
    constructor({ fetch_impl = globalThis.fetch } = {}) {
        this.fetch = fetch_impl
        this.system_ids = new Map()   // name (lower case) -> id | null
        this.jumps_by_pair = new Map()   // "origin:destination" -> jumps | null
        this.inflight = new Map()
    }

    async system_id(name) {
        const key = String(name || '').toLowerCase()
        if (!key) return null
        if (this.system_ids.has(key)) return this.system_ids.get(key)
        const body = await universe_ids([name], this.fetch)
        if (!body) return null   // not cached: try again next time
        const match = find_named(body, 'systems', key)
        const id = match ? match.id : null
        this.system_ids.set(key, id)
        return id
    }

    // origin / destination: a system ID or a system name. Resolves the jump count, or null when unknown.
    async jumps(origin, destination) {
        const [from, to] = await Promise.all([this.as_id(origin), this.as_id(destination)])
        if (!from || !to) return null
        if (from === to) return 0
        const pair = `${from}:${to}`
        if (this.jumps_by_pair.has(pair)) return this.jumps_by_pair.get(pair)
        if (this.inflight.has(pair)) return this.inflight.get(pair)
        const request = this.ask(from, to).finally(() => this.inflight.delete(pair))
        this.inflight.set(pair, request)
        return request
    }

    async ask(from, to) {
        const pair = `${from}:${to}`
        try {
            const response = await this.fetch(`${ESI}/route/${from}/${to}`, { headers: { Accept: 'application/json', ...ESI_HEADERS } })
            if (!response.ok) return null
            const systems = await response.json()
            const jumps = Array.isArray(systems) && systems.length ? systems.length - 1 : null
            if (this.jumps_by_pair.size >= MAX_PAIRS) this.jumps_by_pair.delete(this.jumps_by_pair.keys().next().value)
            this.jumps_by_pair.set(pair, jumps)
            return jumps
        } catch (e) {
            return null
        }
    }

    as_id(system) {
        if (typeof system === 'number') return Promise.resolve(system)
        return this.system_id(system)
    }
}

module.exports = { RouteFinder }
