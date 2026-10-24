// Small helpers every window's HTML builder shares: escaping, plurals and EVE Image Server URLs. Every
// window builds its HTML as strings for innerHTML, so esc() is the one escaper they all rely on. Shared by
// the windows (global `ui_helpers`, loaded before the page's own scripts) and the node tests (module.exports).
(function (root) {
    const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

    // Safe in element text and in quoted attribute values. null and undefined become ''.
    const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ESCAPES[c])

    // "1 pilot", "3 pilots"; irregular words name their plural: plural(n, 'loss', 'losses').
    const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`

    // EVE Image Server (the windows' CSP allows img-src https://images.evetech.net).
    const IMAGES = 'https://images.evetech.net'
    const id_part = id => encodeURIComponent(id)
    const type_icon = (type_id, size = 64) => `${IMAGES}/types/${id_part(type_id)}/icon?size=${size}`
    const type_render = (type_id, size = 256) => `${IMAGES}/types/${id_part(type_id)}/render?size=${size}`
    const portrait = (character_id, size = 64) => `${IMAGES}/characters/${id_part(character_id)}/portrait?size=${size}`
    // Factions and NPC corporations share the corporation logo endpoint.
    const corporation_logo = (id, size = 64) => `${IMAGES}/corporations/${id_part(id)}/logo?size=${size}`
    const alliance_logo = (id, size = 64) => `${IMAGES}/alliances/${id_part(id)}/logo?size=${size}`

    const api = { esc, plural, IMAGES, type_icon, type_render, portrait, corporation_logo, alliance_logo }
    if (typeof module !== 'undefined' && module.exports) module.exports = api
    else root.ui_helpers = api
})(this)
