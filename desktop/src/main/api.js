// Minmatar Fleet API client. Runs in the main process only: the renderer never sees the token,
// it receives the finished view model.
class ApiError extends Error {
    constructor(status, message) {
        super(message)
        this.status = status
    }
}

// The session is gone (expired or revoked): the one condition that signs the pilot out.
const is_unauthorized = err => !!err && err.status === 401

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
            const err = new ApiError(response.status, `${method} ${path} -> ${response.status}${detail ? `: ${detail}` : ''}`)
            err.detail = detail || null   // the API's own wording, safe to show the pilot
            throw err
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

    // The Campaigns window: the pilot's live campaign, its systems and who flew in the last hour.
    campaign_overlay() {
        return this.get('/api/campaigns/overlay')
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

    // Recent fleets (with the pilot's own losses and their SRP state) and ship sign-ups. Polled.
    my_fleets() {
        return this.request('GET', '/api/fleets/window/mine', { etag: true })
    }

    // In-game destination for one of the pilot's characters (needs the Desktop scope group).
    set_waypoint(character_id, destination_id) {
        return this.request('POST', `/api/eveonline/characters/${Number(character_id)}/waypoint`, {
            body: { destination_id: Number(destination_id), clear_other_waypoints: true },
        })
    }

    preping(fleet_id) {
        return this.request('POST', `/api/fleets/${Number(fleet_id)}/preping`)
    }

    // Start tracking: the API checks the FC's in-game fleet over ESI and pings Discord.
    start_fleet(fleet_id, fc_character_id) {
        return this.request('POST', `/api/fleets/${Number(fleet_id)}/tracking`, {
            body: fc_character_id ? { fc_character_id: Number(fc_character_id) } : {},
        })
    }

    // Signing out must not leave one pilot's cached windows for the next.
    forget_cached() {
        this.etags.clear()
    }

    // Intel window (see intel.js in the renderer). The paste goes to the server only when the
    // pilot clicks Share; preview parses it without saving.
    intel_recent() {
        return this.get('/api/intel/recent')
    }

    intel_map() {
        return this.get('/api/intel/map', { auth: false })
    }

    intel_preview(text, kind) {
        return this.request('POST', '/api/intel/reports/preview', { body: { text, kind: kind || null } })
    }

    intel_share({ text, kind, system, note, character_name }) {
        return this.request('POST', '/api/intel/reports', { body: { text, kind: kind || null, system, note: note || '', character_name: character_name || null } })
    }

    intel_report(report_id) {
        return this.get(`/api/intel/reports/${encodeURIComponent(report_id)}`)
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
                fc_user_id: fleet.fleet_commander,
                doctrine: doctrine_names[i],
                fc_character_id: character ? character.character_id : null,
                fc_name: character ? character.character_name : (profile ? profile.username : 'Unknown FC'),
                url: `${web_url}/fleets/upcoming/${fleet.id}`,
            }
        })
        .sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
}

// Campaign overlay -> what the Campaigns window draws, or null when no campaign is live.
async function load_campaign(api, web_url) {
    const { campaign } = await api.campaign_overlay()
    if (!campaign) return null
    return {
        slug: campaign.slug,
        name: campaign.name,
        week_index: campaign.week_index,
        week_count: campaign.week_count,
        url: `${web_url}/campaigns/${encodeURIComponent(campaign.slug)}`,
        systems: campaign.systems.map(system => ({
            id: system.system_id,
            name: system.name,
            holder: ['minmatar', 'amarr'].includes(system.holder) ? system.holder : null,
            objective: system.objective_label,
            progress: system.progress_percent,
            // The rows are the week's objectives, so the move is the week's. A backend
            // from before change_week only has the day's, and says so.
            change: 'change_week' in system ? system.change_week : system.change_24h,
            change_period: 'change_week' in system ? 'week' : '24h',
            change_24h: system.change_24h,
            flipped: ['captured', 'lost'].includes(system.flipped) ? system.flipped : null,
            detail: system.detail || '',
        })),
        active_window_minutes: campaign.active_window_minutes,
        pilots: campaign.active_pilots.map(pilot => ({
            character_id: pilot.character_id,
            name: pilot.character_name,
            system: pilot.system,
            last_at: pilot.last_at,
            kills: pilot.kills,
            losses: pilot.losses,
            complexes: pilot.complexes,
            advantage_sites: pilot.advantage_sites,
            in_fleet: pilot.in_fleet,
        })),
    }
}

module.exports = { ApiClient, ApiError, is_unauthorized, load_upcoming_fleets, load_campaign, FLEET_TYPE_LABELS }
