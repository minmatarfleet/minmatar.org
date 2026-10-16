// Time formatting for fleet rows. EVE time is UTC. Shared by the window (global `fleet_format`)
// and the node tests (module.exports).
(function (root) {
    const DAY_MS = 86_400_000
    const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const pad = n => String(n).padStart(2, '0')

    function eve_time(iso) {
        const d = new Date(iso)
        return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
    }

    // Day headings follow EVE (UTC) days, the same clock pilots use in fleet pings.
    function day_label(iso, now = new Date()) {
        const d = new Date(iso)
        const day = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate())
        const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate())
        const diff = Math.round((day - today) / DAY_MS)
        if (diff === 0) return 'Today'
        if (diff === 1) return 'Tomorrow'
        if (diff === -1) return 'Yesterday'
        return `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`
    }

    function countdown(iso, now = new Date()) {
        let s = Math.round((new Date(iso) - now) / 1000)
        const past = s < 0
        s = Math.abs(s)
        const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60
        let text
        if (d > 0) text = `${d}d ${h}h`
        else if (h > 0) text = `${h}h ${pad(m)}m`
        else if (m > 0) text = `${m}m ${pad(sec)}s`
        else text = `${sec}s`
        return past ? `started ${text} ago` : `in ${text}`
    }

    function group_by_day(fleets, now = new Date()) {
        const groups = []
        for (const fleet of fleets) {
            const label = fleet.live ? 'Live now' : day_label(fleet.start_time, now)
            let group = groups.find(g => g.label === label)
            if (!group) {
                group = { label, fleets: [] }
                fleet.live ? groups.unshift(group) : groups.push(group)
            }
            group.fleets.push(fleet)
        }
        return groups
    }

    const api = { eve_time, day_label, countdown, group_by_day }
    if (typeof module !== 'undefined' && module.exports) module.exports = api
    else root.fleet_format = api
})(this)
