// Text and bar geometry for the Campaigns window. Shared by the window (global `campaign_format`)
// and the node tests (module.exports).
(function (root) {
    const clamp = value => Math.min(100, Math.max(0, value))

    // The 24h move, rounded to whole points: up is good for every objective (the API inverts the rest).
    function change_tone(change) {
        if (change == null) return 'none'
        const rounded = Math.round(change)
        return rounded > 0 ? 'up' : rounded < 0 ? 'down' : 'steady'
    }

    function change_text(change) {
        if (change == null) return ''
        const rounded = Math.round(change)
        return `${rounded > 0 ? '+' : ''}${rounded === 0 ? 0 : rounded}%`
    }

    // The bar: grey up to where both now and 24h ago agree, then the day's move.
    // A gain is solid from yesterday to now; a loss is the dimmed stretch given up.
    function bar(progress, change) {
        if (progress == null) return { fill: 0, delta_from: 0, delta_width: 0 }
        const now = clamp(progress)
        const was = clamp(progress - (change || 0))
        return { fill: Math.min(now, was), delta_from: Math.min(now, was), delta_width: Math.abs(now - was) }
    }

    const plural = (count, one, many) => `${count} ${count === 1 ? one : many}`

    // "2 kills, in fleet": what a pilot did in the window, most telling first.
    function activity_text(pilot) {
        const parts = []
        if (pilot.kills) parts.push(plural(pilot.kills, 'kill', 'kills'))
        if (pilot.losses) parts.push(plural(pilot.losses, 'loss', 'losses'))
        if (pilot.complexes) parts.push(pilot.complexes === 1 ? 'captured a complex' : `captured ${pilot.complexes} complexes`)
        if (pilot.advantage_sites) parts.push(plural(pilot.advantage_sites, 'advantage site', 'advantage sites'))
        if (pilot.in_fleet) parts.push('in fleet')
        const text = parts.join(', ')
        return text ? text[0].toUpperCase() + text.slice(1) : 'Active'
    }

    function ago_text(iso, now = new Date()) {
        const minutes = Math.max(0, Math.floor((now - new Date(iso)) / 60_000))
        if (minutes < 1) return 'just now'
        if (minutes < 60) return `${minutes} min ago`
        const hours = Math.floor(minutes / 60)
        return `${hours}h ${minutes % 60}m ago`
    }

    const api = { change_tone, change_text, bar, activity_text, ago_text }
    if (typeof module !== 'undefined' && module.exports) module.exports = api
    else root.campaign_format = api
})(this)
