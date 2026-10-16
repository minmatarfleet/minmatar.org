// Minmatar Fleet API client. Runs in the main process only: the renderer never sees the token,
// it receives the finished view model.
class ApiError extends Error {
    constructor(status, message) {
        super(message)
        this.status = status
    }
}

const FLEET_TYPE_LABELS = {
    strategic: 'Strategic',
    non_strategic: 'Non-Strategic',
    training: 'Training',
    npsi: 'NPSI',
    standing: 'Standing',
    gang: 'Gang',
}

const REQUEST_TIMEOUT_MS = 10_000

class ApiClient {
    constructor({ api_url, get_token, fetch_impl = globalThis.fetch, timeout_ms = REQUEST_TIMEOUT_MS }) {
        this.api_url = api_url
        this.get_token = get_token
        this.fetch = fetch_impl
        this.timeout_ms = timeout_ms
        this.doctrine_names = new Map()
        this.etags = new Map()   // path -> { etag, body } for polled reads
    }

    // The token is read and the request built synchronously, so a call made just before sign-out
    // still goes out with the token it started with.
    async request(method, path, { auth = true, body, etag = false } = {}) {
        const headers = { Accept: 'application/json' }
        if (auth) {
            const token = this.get_token()
            if (!token) throw new ApiError(401, 'Not signed in')
            headers.Authorization = `Bearer ${token}`
        }
        const cached = etag ? this.etags.get(path) : null
        if (cached) headers['If-None-Match'] = cached.etag
        const options = { method, headers, signal: AbortSignal.timeout(this.timeout_ms) }
        if (body !== undefined) {
            headers['Content-Type'] = 'application/json'
            options.body = JSON.stringify(body)
        }
        const response = await this.fetch(`${this.api_url}${path}`, options)
        if (etag && response.status === 304 && cached) return { body: cached.body, changed: false }
        if (!response.ok) {
            let detail = ''
            try { detail = (await response.json()).detail || '' } catch (e) {}
            throw new ApiError(response.status, `${method} ${path} -> ${response.status}${detail ? `: ${detail}` : ''}`)
        }
        if (response.status === 204) return null
        let json = null
        try { json = await response.json() } catch (e) { if (etag) throw e }   // some writes answer with an empty body
        if (!etag) return json
        const tag = response.headers && response.headers.get && response.headers.get('etag')
        if (tag) this.etags.set(path, { etag: tag, body: json })
        return { body: json, changed: true }
    }

    get(path, options) {
        return this.request('GET', path, options)
    }

    me() {
        return this.get('/api/users/me')
    }

    // Same list the website's Upcoming Fleets page uses: the "active" filter returns fleets that
    // have not ended yet (future pending fleets plus ones running now).
    fleets() {
        return this.get('/api/fleets/v3?fleet_filter=active')
    }

    // Desktop settings saved on the account (see settings.js). save_ merges: only the keys sent change.
    desktop_settings() {
        return this.get('/api/users/me/desktop-settings')
    }

    save_desktop_settings(values) {
        return this.request('PATCH', '/api/users/me/desktop-settings', { body: { values } })
    }

    // The desktop fleet window (backend fleets/helpers/fleet_window.py). Both are polled, so they send
    // If-None-Match and resolve { body, changed }: an unchanged window costs a 304 and no re-render.
    current_fleet_window() {
        return this.request('GET', '/api/fleets/window/current', { etag: true })
    }

    fleet_window(fleet_id) {
        return this.request('GET', `/api/fleets/${Number(fleet_id)}/window`, { etag: true })
    }

    fleet_composition(fleet_id) {
        return this.get(`/api/fleets/${Number(fleet_id)}/composition`)
    }

    // key is a composition key: "f:<fitting id>" (catalog/doctrine fit) or "m:<fleet fitting id>".
    set_my_ship(fleet_id, character_id, key) {
        const [kind, id] = String(key).split(':')
        const selection = { character_id, fitting_id: null, fleet_fitting_id: null }
        if (kind === 'f') selection.fitting_id = Number(id)
        else if (kind === 'm') selection.fleet_fitting_id = Number(id)
        return this.request('PUT', `/api/fleets/${Number(fleet_id)}/my-ship-volunteers`, { body: { selections: [selection] } })
    }

    refresh_motd(fleet_id) {
        return this.request('POST', `/api/fleets/${Number(fleet_id)}/refresh-motd`)
    }

    // Signing out must not leave one pilot's cached windows for the next.
    forget_cached() {
        this.etags.clear()
    }

    profiles(user_ids) {
        if (!user_ids.length) return Promise.resolve([])
        return this.get(`/api/users/profiles?ids=${user_ids.join(',')}`, { auth: false })
    }

    async doctrine_name(doctrine_id) {
        if (!doctrine_id) return null
        if (!this.doctrine_names.has(doctrine_id)) {
            try {
                const doctrine = await this.get(`/api/doctrines/${doctrine_id}`, { auth: false })
                this.doctrine_names.set(doctrine_id, doctrine.name)
            } catch (e) {
                return null   // a missing doctrine name is cosmetic; don't fail the list
            }
        }
        return this.doctrine_names.get(doctrine_id)
    }
}

// Fleet list -> rows for the overlay, soonest first.
async function load_upcoming_fleets(api, web_url) {
    const fleets = (await api.fleets()).filter(fleet => fleet.fleet_commander)
    const fc_ids = [...new Set(fleets.map(fleet => fleet.fleet_commander))]
    const profiles = await api.profiles(fc_ids)
    const doctrine_names = await Promise.all(fleets.map(fleet => api.doctrine_name(fleet.doctrine_id)))

    return fleets
        .map((fleet, i) => {
            const profile = profiles.find(p => p && p.user_id === fleet.fleet_commander)
            const character = profile && profile.eve_character_profile
            return {
                id: fleet.id,
                type: fleet.type,
                type_label: FLEET_TYPE_LABELS[fleet.type] || fleet.type,
                audience: fleet.audience || null,
                description: fleet.description || '',
                objective: fleet.objective || null,
                location: fleet.location || '',
                start_time: fleet.start_time,
                status: fleet.status || 'pending',
                live: !!fleet.tracking,
                doctrine: doctrine_names[i],
                fc_character_id: character ? character.character_id : null,
                fc_name: character ? character.character_name : (profile ? profile.username : 'Unknown FC'),
                url: `${web_url}/fleets/upcoming/${fleet.id}`,
            }
        })
        .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
}

module.exports = { ApiClient, ApiError, load_upcoming_fleets, FLEET_TYPE_LABELS }
