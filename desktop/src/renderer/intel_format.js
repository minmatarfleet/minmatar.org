// Formatting for the Intel window. Shared by the window (global `intel_format`) and the node tests.
(function (root) {
    const KIND_LABELS = { dscan: 'D-scan', local: 'Local', caps: 'Capital ping', fleet: 'Fleet ping' }
    const STRIP_SIZE = 4   // hulls shown on a row; the rest go behind "+N"
    const IMAGE_HOST = 'https://images.evetech.net'

    // Ships arrive biggest first; split them into the strip and the "+N" list.
    function split_ships(ships, size = STRIP_SIZE) {
        const list = ships || []
        const shown = list.slice(0, size)
        const rest = list.slice(size)
        return { shown, rest, more: rest.reduce((n, ship) => n + ship.count, 0) }
    }

    function ago(iso, now = Date.now()) {
        const minutes = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60_000))
        if (minutes < 60) return `${minutes}m`
        return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
    }

    function jumps_label(jumps) {
        if (jumps == null) return ''
        if (jumps === 0) return 'here'
        return `${jumps} ${jumps === 1 ? 'jump' : 'jumps'}`
    }

    function type_icon(type_id, size = 64) {
        return `${IMAGE_HOST}/types/${encodeURIComponent(type_id)}/icon?size=${size}`
    }

    // Factions and NPC corporations share the corporation logo endpoint.
    function image_url(image, size = 64) {
        if (!image) return null
        if (image.kind === 'type') return type_icon(image.id, size)
        if (image.kind === 'faction' || image.kind === 'corporation') return `${IMAGE_HOST}/corporations/${encodeURIComponent(image.id)}/logo?size=${size}`
        if (image.kind === 'alliance') return `${IMAGE_HOST}/alliances/${encodeURIComponent(image.id)}/logo?size=${size}`
        return null
    }

    // Recent: last 15 minutes, then the rest of the hour, then older.
    function group_by_age(items, now = Date.now()) {
        const buckets = [
            { title: 'Last 15 min', max: 15, items: [] },
            { title: '15 to 60 min', max: 60, items: [] },
            { title: '1 to 2 hours', max: Infinity, items: [] },
        ]
        for (const item of items) {
            const minutes = (now - new Date(item.occurred_at).getTime()) / 60_000
            buckets.find(b => minutes < b.max).items.push(item)
        }
        return buckets.filter(b => b.items.length)
    }

    const api = { KIND_LABELS, STRIP_SIZE, split_ships, ago, jumps_label, type_icon, image_url, group_by_age }
    if (typeof module !== 'undefined' && module.exports) module.exports = api
    else root.intel_format = api
})(this)
