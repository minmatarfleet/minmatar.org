const { test } = require('node:test')
const assert = require('node:assert/strict')
const { IntelMap, within_range } = require('../src/main/intel_map')
const { IntelController, NEW_FOR_MS } = require('../src/main/intel')
const { split_ships, ago, jumps_label, image_url, group_by_age } = require('../src/renderer/intel_format')

// Amamake - Siseide - Bosboger, plus Vard off Amamake. Huola is on the map with no gates.
const MAP = {
    systems: { 1: 'Amamake', 2: 'Siseide', 3: 'Bosboger', 4: 'Vard', 9: 'Huola' },
    edges: { 1: [2, 4], 2: [1, 3], 3: [2], 4: [1] },
}

test('counts jumps from the pilot\'s system, case-insensitively', () => {
    const map = new IntelMap(MAP)
    assert.equal(map.jumps('amamake', 1), 0)
    assert.equal(map.jumps('Amamake', 3), 2)
    assert.equal(map.jumps('Bosboger', 4), 3)
    assert.equal(map.jumps('Amamake', 9), null)        // no route
    assert.equal(map.jumps('Jita', 2), null)           // origin off the map
    assert.equal(map.jumps(null, 2), null)
})

test('caches one search per origin', () => {
    const map = new IntelMap(MAP)
    const first = map.distances_from(1)
    assert.equal(map.distances_from(1), first)
})

test('range keeps rows with an unknown distance', () => {
    assert.equal(within_range({ jumps: 6 }, 5), false)
    assert.equal(within_range({ jumps: 5 }, 5), true)
    assert.equal(within_range({ jumps: null }, 5), true)
    assert.equal(within_range({ jumps: 40 }, null), true)
})

test('splits the hull strip from the "+N" list', () => {
    const ships = [5, 4, 3, 2, 1, 6].map((count, i) => ({ type_id: i, name: `S${i}`, count }))
    const { shown, rest, more } = split_ships(ships)
    assert.deepEqual(shown.map(s => s.name), ['S0', 'S1', 'S2', 'S3'])
    assert.deepEqual(rest.map(s => s.name), ['S4', 'S5'])
    assert.equal(more, 7)
    assert.equal(split_ships(null).more, 0)
})

test('formats ages, jumps and image urls', () => {
    const now = Date.parse('2026-10-16T20:00:00Z')
    assert.equal(ago('2026-10-16T19:57:30Z', now), '2m')
    assert.equal(ago('2026-10-16T18:10:00Z', now), '1h 50m')
    assert.equal(jumps_label(0), 'here')
    assert.equal(jumps_label(1), '1 jump')
    assert.equal(jumps_label(null), '')
    assert.equal(image_url({ kind: 'type', id: 597 }), 'https://images.evetech.net/types/597/icon?size=64')
    assert.equal(image_url({ kind: 'faction', id: 500003 }, 32), 'https://images.evetech.net/corporations/500003/logo?size=32')
    assert.equal(image_url(null), null)
    const groups = group_by_age([
        { occurred_at: '2026-10-16T19:55:00Z' },
        { occurred_at: '2026-10-16T19:30:00Z' },
        { occurred_at: '2026-10-16T18:30:00Z' },
        { occurred_at: '2026-10-16T19:50:00Z' },
    ], now)
    assert.deepEqual(groups.map(g => [g.title, g.items.length]), [['Last 15 min', 2], ['15 to 60 min', 1], ['1 to 2 hours', 1]])
})

function fake_api(overrides = {}) {
    const calls = []
    let recent = { items: [] }
    const api = {
        calls,
        set_recent: items => { recent = { items } },
        intel_map: async () => { calls.push('map'); return MAP },
        intel_recent: async () => { calls.push('recent'); return recent },
        intel_preview: async (text, kind) => { calls.push(['preview', kind]); return { kind: kind || 'dscan', lines: 3, summary: { ships: 2, capsules: 0, other: 1, hulls: [] } } },
        intel_share: async body => { calls.push(['share', body]); return { report_id: 'abc123' } },
        intel_report: async id => ({ report_id: id, kind: 'dscan', system_id: 2, system_name: 'Siseide', raw: 'a\nb\n', summary: {} }),
        ...overrides,
    }
    return api
}

function controller(api, extra = {}) {
    let now = Date.parse('2026-10-16T20:00:00Z')
    const views = []
    const notified = []
    const c = new IntelController({
        api,
        web_url: 'https://web.example',
        on_change: view => views.push(view),
        notify: item => notified.push(item.id),
        now: () => now,
        ...extra,
    })
    return { c, views, notified, tick: ms => { now += ms } }
}

const ping = (id, system_id) => ({ id, kind: 'caps', is_ping: true, system_id, system_name: 'X', occurred_at: '2026-10-16T19:59:00Z', ships: [] })

test('annotates jumps from the client in front and only notifies new pings in range', async () => {
    const api = fake_api()
    const { c, notified, tick } = controller(api)
    c.set_origin({ character: 'Ardo Kesh', system: 'Amamake' })
    api.set_recent([ping('c:1', 2)])
    await c.refresh()
    assert.deepEqual(notified, [])                      // the first load is history, not news
    assert.equal(c.items[0].jumps, 1)
    assert.equal(c.items[0].is_new, false)

    tick(30_000)
    api.set_recent([ping('c:3', 3), ping('c:2', 99), ping('c:1', 2)])
    c.set_options({ range: 1 })
    await c.refresh()
    // c:3 is 2 jumps out (outside range 1); c:2 is off the map, so its distance is unknown and it counts.
    assert.deepEqual(notified, ['c:2'])
    assert.equal(c.items.find(i => i.id === 'c:3').is_new, true)

    tick(NEW_FOR_MS + 1)
    c.annotate()
    assert.equal(c.items.find(i => i.id === 'c:3').is_new, false)
    assert.equal(api.calls.filter(call => call === 'map').length, 1)

    c.set_options({ alerts: false })
    api.set_recent([ping('c:4', 1)])
    await c.refresh()
    assert.deepEqual(notified, ['c:2'])
})

test('moving to another system re-counts jumps without a refetch', async () => {
    const api = fake_api()
    const { c } = controller(api)
    api.set_recent([ping('c:1', 3)])
    c.set_origin({ character: 'A', system: 'Amamake' })
    await c.refresh()
    assert.equal(c.items[0].jumps, 2)
    c.set_origin({ character: 'A', system: 'Bosboger' })
    assert.equal(c.items[0].jumps, 0)
    assert.equal(api.calls.filter(call => call === 'recent').length, 1)
})

test('paste -> preview -> share keeps the paste out of the pushed state', async () => {
    const api = fake_api()
    const { c, views } = controller(api)
    c.set_origin({ character: 'Ardo Kesh', system: 'Amamake' })
    await c.paste('597\tA\tPunisher\t1 km')
    assert.equal(c.draft.status, 'ready')
    assert.equal(c.draft.system, 'Amamake')
    assert.ok(views.every(v => !JSON.stringify(v).includes('Punisher\t')))

    c.edit_draft({ note: 'on the gate', system: 'Siseide' })
    c.set_origin({ character: 'Ardo Kesh', system: 'Vard' })   // an edited system sticks
    assert.equal(c.draft.system, 'Siseide')

    const url = await c.share()
    assert.equal(url, 'https://web.example/intel/scans/abc123')
    const [, body] = api.calls.find(call => call[0] === 'share')
    assert.deepEqual(body, { text: '597\tA\tPunisher\t1 km', kind: 'dscan', system: 'Siseide', note: 'on the gate', character_name: 'Ardo Kesh' })
    assert.equal(c.draft.status, 'shared')
    assert.equal(c.url_for('abc123'), url)
    assert.equal(c.url_for('someone-elses'), null)
})

test('a rejected share shows the API\'s reason and keeps the draft', async () => {
    const err = Object.assign(new Error('400'), { status: 400, detail: 'Pick the system this is from.' })
    const api = fake_api({ intel_share: async () => { throw err } })
    const { c } = controller(api)
    await c.paste('Ardo Kesh')
    assert.equal(await c.share(), null)
    assert.equal(c.draft.status, 'ready')
    assert.equal(c.draft.error, 'Pick the system this is from.')
})

test('an empty clipboard says so instead of calling the API', async () => {
    const api = fake_api()
    const { c } = controller(api)
    await c.paste('   ')
    assert.equal(c.draft.status, 'error')
    assert.equal(api.calls.length, 0)
})

test('a 401 anywhere signs out', async () => {
    let signed_out = 0
    const api = fake_api({ intel_recent: async () => { throw Object.assign(new Error('401'), { status: 401 }) } })
    const { c } = controller(api, { on_unauthorized: () => { signed_out++ } })
    await c.refresh()
    assert.equal(signed_out, 1)
})

test('report detail trims the raw paste and links only known reports', async () => {
    const api = fake_api()
    const { c } = controller(api)
    c.set_origin({ character: 'A', system: 'Amamake' })
    await c.load_map()
    await c.open_report('r1')
    assert.equal(c.detail.status, 'ready')
    assert.equal(c.detail.raw, undefined)
    assert.equal(c.detail.raw_lines, 2)
    assert.equal(c.detail.jumps, 1)
    assert.equal(c.url_for('r1'), 'https://web.example/intel/scans/r1')
})
