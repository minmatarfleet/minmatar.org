// The backend writes test/contracts/*.json from its real endpoints (backend/app/contracts.py), and its
// tests fail when an endpoint stops matching them. These tests feed the same files through the desktop's
// own loaders and views, so a payload change that would break installed apps fails on one side or the
// other. A changed file means a desktop-visible change: see .claude/rules/desktop-release.md.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const path = require('path')
const { ApiClient, load_campaign, load_upcoming_fleets } = require('../src/main/api')
const { FleetWindow } = require('../src/main/fleet_window')
const { IntelController } = require('../src/main/intel')
const campaign_view = require('../src/renderer/campaign_view')
const { fleet_tab, upcoming_tab, recent_tab } = require('../src/renderer/fleet_view')
const { recent_view, detail_view } = require('../src/renderer/intel_view')

const contract = name => JSON.parse(fs.readFileSync(path.join(__dirname, 'contracts', `${name}.json`), 'utf8'))
// The backend seeds contract data at 2026-01-17 18:00 UTC.
const NOW = Date.parse('2026-01-17T18:00:00Z')
const WEB = 'https://web.example'

// Nothing the views print should come from a field that wasn't there.
function assert_clean(html) {
    assert.equal(typeof html, 'string')
    assert.doesNotMatch(html, /undefined|NaN|\[object Object\]/)
}

test('every contract file is used here', () => {
    const files = fs.readdirSync(path.join(__dirname, 'contracts')).map(f => f.replace(/\.json$/, '')).sort()
    assert.deepEqual(files, ['campaign_overlay', 'fleet_window_fc', 'fleet_window_member', 'intel_recent', 'intel_report', 'my_fleets', 'upcoming_fleets'])
})

test('campaign overlay: every row and pilot reaches the Campaigns window', async () => {
    const payload = contract('campaign_overlay')
    const campaign = await load_campaign({ campaign_overlay: async () => payload }, WEB)
    assert.equal(campaign.systems.length, payload.campaign.systems.length)
    assert.equal(campaign.url, `${WEB}/campaigns/${payload.campaign.slug}`)
    for (const system of campaign.systems) {
        assert.equal(typeof system.objective, 'string')
        assert.equal(system.change_period, 'week')
    }
    const html = campaign_view.content({ campaign, campaign_updated_at: payload.campaign.active_pilots[0].last_at })
    assert_clean(html)
    assert.equal((html.match(/class="system"/g) || []).length, payload.campaign.systems.length)
    for (const pilot of payload.campaign.active_pilots) assert.ok(html.includes(pilot.character_name))
})

test('upcoming fleets: one request builds the schedule, FC and doctrine named by the backend', async () => {
    const payload = contract('upcoming_fleets')
    const urls = []
    const api = new ApiClient({
        api_url: 'https://api.example',
        get_token: () => 'jwt',
        fetch_impl: async url => {
            urls.push(url)
            return { ok: true, status: 200, json: async () => (url.includes('/fleets/v3') ? payload : []) }
        },
    })
    const rows = await load_upcoming_fleets(api, WEB)
    assert.deepEqual(urls, ['https://api.example/api/fleets/v3?fleet_filter=active'])
    assert.equal(rows.length, payload.length)
    for (const row of rows) {
        assert.ok(row.fc_name && row.fc_name !== 'Unknown FC')
        assert.ok(row.fc_character_id)
    }
    const html = upcoming_tab({ loaded: true, opened: null, signups: {}, reminders: [] }, rows).main
    assert_clean(html)
    for (const row of rows) assert.ok(html.includes(row.fc_name))
})

function fleet_window({ current = null, windows = {}, mine = { fleets: [], srp_owed: 0, signups: [] } } = {}) {
    const fw = new FleetWindow({
        api: {
            async current_fleet_window() { return { body: { window: current }, changed: true } },
            async my_fleets() { return { body: mine, changed: true } },
            async fleet_window(id) { return { body: windows[id], changed: true } },
        },
        routes: { async jumps() { return 2 } },
        web_url: WEB,
        clipboard: { writeText() {} },
        open_external() {},
        notify() {},
        store: { get() {}, set() {} },
        now: () => NOW,
        timers: { setTimeout: () => 0, clearTimeout() {} },
    })
    const snapshots = []
    fw.on('change', s => snapshots.push(s))
    return { fw, last: () => snapshots.at(-1) }
}

test('fleet window, member: the pilot sees their own ship and the FC, never the roster', async () => {
    const { window } = contract('fleet_window_member')
    const { fw, last } = fleet_window({ current: window })
    fw.set_user(7001, window.me.character_ids[0])
    await fw.poll()
    const s = last()
    assert.equal(s.focus.fleet.mode, 'member')
    assert.equal(s.focus.fleet.fleet.id, window.fleet.id)
    const parts = fleet_tab(s)
    assert_clean(parts.main)
    assert.ok(parts.main.includes(window.fleet.fc_name))
    // A pilot in the fleet sees the round being fought.
    assert.match(parts.main, /Fighting now/)
})

test('fleet window, FC: the summary, ships and roster render', async () => {
    const window = contract('fleet_window_fc')
    const { fw, last } = fleet_window({ current: window })
    fw.set_user(7002, window.fleet.fc_character_id)
    await fw.poll()
    const s = last()
    assert.equal(s.focus.fleet.mode, 'fc')
    for (const fc_view of ['overview', 'pilots', 'kills']) assert_clean(fleet_tab(s, { fc_view }).main)
    assert.ok(fleet_tab(s, { fc_view: 'overview' }).main.includes(window.ships[0].ship_name))
    // The fleet has rounds: Kills becomes Fights, naming the round being fought.
    assert.match(fleet_tab(s, { fc_view: 'overview' }).main, /Fights <span class="eve-dim">E2<\/span>/)
    const fights = fleet_tab(s, { fc_view: 'kills' }).main
    assert.match(fights, /fw-round is-fighting/)
    assert.equal((fights.match(/data-h="/g) || []).length, window.fights.latest.bins.length * 2)
    assert.match(fights, /Engagement 1 <span class="eve-dim">/)
})

test('my fleets: recent fleets with losses and their SRP state', async () => {
    const mine = contract('my_fleets')
    const { fw, last } = fleet_window({ mine })
    fw.set_user(7001, mine.signups[0].character_id)
    await fw.poll()
    const s = last()
    assert.equal(s.recent.srp_owed, mine.srp_owed)
    const html = recent_tab(s).main
    assert_clean(html)
    // One loss still owes SRP (File SRP for that killmail); the other was paid.
    const owed = mine.fleets[0].my_losses.filter(loss => loss.srp_status === 'none')
    assert.equal(owed.length, 1)
    assert.ok(html.includes(`data-fleet-command="fleet:srp" data-id="${owed[0].killmail_id}"`))
    assert.match(html, /SRP not filed · SRP paid 42M/)
    assert.match(html, /Sat 17 Jan · 20m · you lost 2/)
    assert.ok(html.includes(mine.fleets[0].title))
})

const MAP = { systems: { 30002537: 'Amamake', 30003070: 'Sosala' }, edges: { 30002537: [30003070], 30003070: [30002537] } }

async function intel(api) {
    const views = []
    const c = new IntelController({ api: { intel_map: async () => MAP, ...api }, web_url: WEB, on_change: v => views.push(v), now: () => NOW })
    c.set_origin({ character: 'Pilot', system: 'Amamake' })
    return { c, last: () => views.at(-1) }
}

test('intel recent: reports and pings reach the sheet', async () => {
    const payload = contract('intel_recent')
    const { c, last } = await intel({ intel_recent: async () => payload })
    await c.refresh()
    const view = last()
    assert.equal(view.items.length, payload.items.length)
    const html = recent_view(view, view.items)
    assert_clean(html)
    for (const item of payload.items) assert.ok(html.includes(item.system_name))
})

test('intel report: a shared d-scan opens with its breakdown and site link', async () => {
    const report = contract('intel_report')
    const { c, last } = await intel({ intel_recent: async () => ({ items: [] }), intel_report: async () => report })
    await c.refresh()
    await c.open_report(report.report_id)
    const view = last()
    assert.equal(view.detail.status, 'ready')
    assert.equal(view.detail.url, `${WEB}/intel/scans/${report.report_id}`)
    const html = detail_view(view)
    assert_clean(html)
    assert.ok(html.includes(report.reporter_name))
})
