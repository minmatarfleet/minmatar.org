const { test } = require('node:test')
const assert = require('node:assert/strict')
const { universe_ids, find_named, ESI_HEADERS } = require('../src/main/esi')
const { version } = require('../package.json')

test('name lookups identify the app, pin the API version and send the names', async () => {
    let seen
    const body = await universe_ids(['Hek', 'Kesra Lund'], async (url, options) => {
        seen = { url, options }
        return { ok: true, json: async () => ({ systems: [{ id: 30002053, name: 'Hek' }] }) }
    })
    assert.equal(seen.url, 'https://esi.evetech.net/universe/ids')
    assert.equal(seen.options.method, 'POST')
    assert.equal(seen.options.body, '["Hek","Kesra Lund"]')
    assert.equal(seen.options.headers['User-Agent'], ESI_HEADERS['User-Agent'])
    assert.ok(ESI_HEADERS['User-Agent'].startsWith(`MinmatarFleetDesktop/${version} `))
    assert.match(seen.options.headers['X-Compatibility-Date'], /^\d{4}-\d\d-\d\d$/)
    assert.deepEqual(find_named(body, 'systems', 'hek'), { id: 30002053, name: 'Hek' })
    assert.equal(find_named(body, 'characters', 'Hek'), null)
})

test('no answer from ESI is null (callers retry later), never an empty result to cache', async () => {
    assert.equal(await universe_ids(['Hek'], async () => ({ ok: false, status: 420 })), null)
    assert.equal(await universe_ids(['Hek'], async () => { throw new Error('offline') }), null)
    assert.equal(await universe_ids(['Hek'], async () => ({ ok: true, json: async () => { throw new SyntaxError('bad json') } })), null)
    assert.equal(find_named(null, 'systems', 'Hek'), null)
})
