const { test } = require('node:test')
const assert = require('node:assert/strict')
const { RouteFinder } = require('../src/main/route')

function fake_esi(calls) {
    return async (url, options = {}) => {
        calls.push({ url, ua: options.headers['User-Agent'], date: options.headers['X-Compatibility-Date'] })
        if (url.endsWith('/universe/ids')) {
            const [name] = JSON.parse(options.body)
            return { ok: true, json: async () => ({ systems: name === 'Hek' ? [{ id: 30002053, name: 'Hek' }] : [] }) }
        }
        return { ok: true, json: async () => [30002053, 30002054, 30002056, 30002537] }
    }
}

test('jumps = route length - 1; every pair and name is asked once, with the app identified', async () => {
    const calls = []
    const routes = new RouteFinder({ fetch_impl: fake_esi(calls) })
    assert.equal(await routes.jumps('Hek', 30002537), 3)
    assert.equal(await routes.jumps('hek', 30002537), 3)
    await Promise.all([routes.jumps(30002053, 30002537), routes.jumps(30002053, 30002537)])
    assert.deepEqual(calls.map(c => c.url), ['https://esi.evetech.net/universe/ids', 'https://esi.evetech.net/route/30002053/30002537'])
    assert.ok(calls.every(c => /MinmatarFleetDesktop/.test(c.ua) && c.date))
})

test('same system is 0 jumps with no call; unknown names give null', async () => {
    const calls = []
    const routes = new RouteFinder({ fetch_impl: fake_esi(calls) })
    assert.equal(await routes.jumps(30002537, 30002537), 0)
    assert.equal(await routes.jumps('Nowhere', 30002537), null)
    assert.equal(calls.filter(c => c.url.includes('/route/')).length, 0)
})
