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

class ApiClient {
    constructor({ api_url, get_token, fetch_impl = globalThis.fetch }) {
        this.api_url = api_url
        this.get_token = get_token
        this.fetch = fetch_impl
        this.doctrine_names = new Map()
    }

    async get(path, { auth = true } = {}) {
        const headers = { Accept: 'application/json' }
        if (auth) {
            const token = this.get_token()
            if (!token) throw new ApiError(401, 'Not signed in')
            headers.Authorization = `Bearer ${token}`
        }
        const response = await this.fetch(`${this.api_url}${path}`, { headers })
        if (!response.ok) {
            let detail = ''
            try { detail = (await response.json()).detail || '' } catch (e) {}
            throw new ApiError(response.status, `GET ${path} -> ${response.status}${detail ? `: ${detail}` : ''}`)
        }
        return response.json()
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
            change: system.change_24h,
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

module.exports = { ApiClient, ApiError, load_upcoming_fleets, load_campaign, FLEET_TYPE_LABELS }
