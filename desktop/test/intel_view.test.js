// The Intel window's HTML, fed from GET /api/intel/recent items through main's IntelController, the same
// path the window's data takes.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { IntelController } = require('../src/main/intel')
const { in_range, recent_view, all_view, draft_view, detail_view, RECENT_ROWS } = require('../src/renderer/intel_view')

const MAP = { systems: { 1: 'Amamake', 2: 'Siseide', 3: 'Bosboger' }, edges: { 1: [2], 2: [1, 3], 3: [2] } }
const NOW = Date.parse('2026-10-16T20:00:00Z')

// RecentItemSchema (backend intel/router.py).
const item = (id, extra = {}) => ({
    id, kind: 'dscan', is_ping: false, report_id: id.replace('r:', ''), system_id: 2, system_name: 'Siseide',
    occurred_at: '2026-10-16T19:55:00Z', source: 'Kesra Lund', note: '', count: 7, summary: '7 ships',
    image: { kind: 'type', id: 24690 }, standings: null,
    ships: [1, 2, 3, 4, 5].map(i => ({ type_id: 600 + i, name: `Hull ${i}`, count: i })), ...extra,
})

async function intel_state(items) {
    const views = []
    const c = new IntelController({
        api: { intel_map: async () => MAP, intel_recent: async () => ({ items }) },
        web_url: 'https://web.example', on_change: view => views.push(view), now: () => NOW,
    })
    c.set_origin({ character: 'Kesra Lund', system: 'Amamake' })
    await c.refresh()
    return views[views.length - 1]
}

test('recent: the paste bar, nearest rows first four, and a Show all link', async () => {
    const items = ['r:a', 'r:b', 'r:c', 'r:d', 'r:e'].map(id => item(id))
    const intel = await intel_state(items)
    const html = recent_view(intel, intel.items)
    assert.match(html, /Copy d-scan or Local<\/span><kbd>Ctrl C<\/kbd>/)
    assert.doesNotMatch(html, /data-action="paste"/)
    assert.match(html, /in <b>Amamake<\/b>/)
    assert.equal((html.match(/class="intel-row"/g) || []).length, RECENT_ROWS)
    assert.match(html, /Show all 5 →/)
    assert.match(html, /1 jump/)
    // Four hulls on the strip, the fifth behind "+5".
    assert.match(html, /aria-label="5 more ships: Hull 5 5">\+5</)
    assert.match(html, /5 more ships/)
})

test('draft: titled from the copy that opened it, then from the preview', () => {
    assert.match(draft_view({ draft: { status: 'loading', kind: null, detected: { kind: 'dscan', count: 38 } } }), /<h2>Scan detected · 38 items<\/h2>/)
    assert.match(draft_view({ draft: { status: 'loading', kind: null, detected: { kind: 'local', count: 1 } } }), /<h2>Local detected · 1 pilot<\/h2>/)
    assert.match(draft_view({ draft: { status: 'ready', kind: 'dscan', lines: 40, summary: { ships: 1, capsules: 0, other: 0, hulls: [] } } }), /<h2>Scan detected · 40 items<\/h2>/)
    assert.match(draft_view({ draft: { status: 'loading', kind: null } }), /<h2>New report<\/h2>/)
})

test('rows escape what pilots typed', async () => {
    const intel = await intel_state([item('r:x', { source: '<img src=x>', note: 'on "the" gate', system_name: 'A&B' })])
    const html = recent_view(intel, intel.items)
    assert.ok(!html.includes('<img src=x>'))
    assert.match(html, /&lt;img src=x&gt; · “on &quot;the&quot; gate”/)
    assert.match(html, /A&amp;B/)
})

test('range keeps rows with an unknown distance', () => {
    assert.equal(in_range({ jumps: 6 }, 5), false)
    assert.equal(in_range({ jumps: null }, 5), true)
    assert.equal(in_range({ jumps: 9 }, null), true)
})

test('show all filters reports and pings', async () => {
    const ping = item('c:1', { kind: 'caps', is_ping: true, report_id: null, source: '', ships: [{ type_id: 23757, name: 'Archon', count: 1 }], summary: 'Archon' })
    const intel = await intel_state([item('r:a'), ping])
    assert.match(all_view(intel, intel.items, 'all'), /aria-pressed="true">All <span>2<\/span>/)
    const pings = all_view(intel, intel.items, 'pings')
    assert.equal((pings.match(/class="intel-row intel-row--compact"/g) || []).length, 1)
    assert.match(pings, /intel-thumb--ping/)
    assert.match(all_view({ ...intel, items: [] }, [], 'reports'), /Nothing here in the last 2 hours/)
})

test('nothing yet, nothing in range, and offline', async () => {
    assert.match(recent_view({ items: [], updated_at: null }, []), /Loading intel…/)
    assert.match(recent_view({ items: [], updated_at: '2026-10-16T20:00:00Z' }, []), /Nothing in range in the last 2 hours/)
    assert.match(recent_view({ items: [], error: 'Could not reach <x>' }, []), /<p class="eve-error">Could not reach &lt;x&gt;<\/p>/)
})

test('draft: preview counts, then the shared state', () => {
    const summary = { ships: 3, capsules: 1, other: 2, classes: [{ name: 'Battleship', count: 3, hulls: [] }], hulls: [{ type_id: 641, name: 'Megathron', count: 3 }] }
    const ready = draft_view({ draft: { status: 'ready', kind: 'dscan', lines: 6, summary } })
    assert.match(ready, /<h2>Scan detected · 6 items<\/h2>/)
    assert.match(ready, /<b>3<\/b> battleships/)
    assert.match(ready, /3 ships · 1 capsule · 2 other/)
    assert.match(ready, /data-action="share" >Share to intel/)
    const shared = draft_view({ draft: { status: 'shared', kind: 'dscan', lines: 6, summary, report_id: 'abc' } })
    assert.match(shared, /Shared · link copied/)
    assert.match(shared, /data-report="abc"/)
    assert.match(draft_view({ draft: { status: 'error', error: 'The clipboard is empty.' } }), /Copy a d-scan or Local in EVE to try again/)
})

test('report: d-scan tabs and a resolved Local', () => {
    const report = {
        status: 'ready', report_id: 'r1', kind: 'dscan', system_name: 'Siseide', jumps: 1, reporter_name: 'Kesra', created_at: '2026-10-16T19:50:00Z',
        note: '', raw_preview: 'a\n<b>', raw_lines: 14,
        summary: { ships: 3, capsules: 0, other: 1, classes: [{ name: 'Battleship', count: 3, hulls: [{ type_id: 641, name: 'Megathron', count: 3 }] }], other_items: [] },
    }
    assert.match(detail_view({ detail: report }), /Megathron/)
    assert.match(detail_view({ detail: report }, 'raw'), /<pre class="intel-raw">a\n&lt;b&gt;\n… 2 more lines<\/pre>/)
    const local = {
        ...report, kind: 'local',
        summary: { pilots: 4, resolved: true, unknown: 0, standings: { hostile: 2, neutral: 1, friendly: 1 }, militia: { amarr: 2, none: 1, minmatar: 1 }, alliances: [{ id: 99, name: 'Foes', standing: 'hostile', count: 2 }] },
    }
    const html = detail_view({ detail: local })
    assert.match(html, /data-flex="2"/)
    assert.match(html, /alliances\/99\/logo\?size=64/)
    assert.match(html, /corporations\/500003\/logo/)
    // Older backends send no blocs: no section.
    assert.doesNotMatch(html, /By bloc/)
})

test('report: Local groups pilots into blocs when the backend sends them', () => {
    const local = {
        status: 'ready', report_id: 'r2', kind: 'local', system_name: 'Amamake', reporter_name: 'Kesra', created_at: '2026-10-16T19:50:00Z', note: '',
        summary: {
            pilots: 14, resolved: true, unknown: 0, standings: { hostile: 0, neutral: 14, friendly: 0 }, militia: { amarr: 0, none: 14, minmatar: 0 },
            alliances: [{ id: 99004901, name: 'Snuffed Out', standing: 'neutral', count: 9, bloc: { id: 1, name: 'Snuffed Out', likely: false } }],
            blocs: [{ id: 1, name: 'Snuffed Out', likely: false, count: 14, groups: [
                { kind: 'alliance', id: 99004901, name: 'Snuffed Out', count: 9, likely: false },
                { kind: 'alliance', id: 99010022, name: 'Scary <Wormhole> People', count: 5, likely: true },
            ] }],
        },
    }
    const html = detail_view({ detail: local })
    assert.match(html, /By bloc/)
    assert.match(html, /alliances\/99004901\/logo\?size=64/)
    assert.match(html, /Scary &lt;Wormhole&gt; People 5 <small>likely<\/small>/)
    assert.ok(html.indexOf('By bloc') < html.indexOf('By alliance'))
})
