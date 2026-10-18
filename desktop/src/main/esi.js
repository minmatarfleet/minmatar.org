// The public ESI calls the desktop makes itself (no token, no character data): name -> ID lookups and
// jump counts. One place for ESI etiquette (docs/desktop/ccp-third-party-guidelines.md rule 12): identify
// the app, pin the API version, and let callers cache answers for the session.
const ESI = 'https://esi.evetech.net'

const ESI_HEADERS = {
    'User-Agent': `MinmatarFleetDesktop/${require('../../package.json').version} (+https://github.com/minmatarfleet/minmatar.org)`,
    'X-Compatibility-Date': '2025-08-26',
}

// POST /universe/ids: { characters: [{ id, name }], systems: [...], ... } for the names ESI knows, or null
// when ESI didn't answer (offline, an error status): callers cache answers, never a null.
async function universe_ids(names, fetch_impl = globalThis.fetch) {
    try {
        const response = await fetch_impl(`${ESI}/universe/ids`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...ESI_HEADERS },
            body: JSON.stringify(names),
        })
        if (!response.ok) return null
        return await response.json()
    } catch (e) {
        return null
    }
}

// The entry in a universe_ids category ('characters', 'systems', ...) whose name matches, ignoring case.
function find_named(body, category, name) {
    const key = String(name).toLowerCase()
    return ((body && body[category]) || []).find(entry => String(entry.name).toLowerCase() === key) || null
}

module.exports = { ESI, ESI_HEADERS, universe_ids, find_named }
