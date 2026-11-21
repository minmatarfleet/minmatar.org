// The Campaigns window's HTML, fed from a GET /api/campaigns/overlay payload through api.js load_campaign,
// the same path the window's data takes.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { load_campaign } = require('../src/main/api')
const { content, render_system, render_pilots, selected_campaign } = require('../src/renderer/campaign_view')

const system = (extra = {}) => ({
    system_id: 30002537, name: 'Amamake', holder: 'minmatar', objective_label: 'Hold the complexes', progress_percent: 42,
    change_week: 8.4, change_24h: -2, flipped: null, detail: '42 / 100 VP', ...extra,
})
const pilot = (extra = {}) => ({
    character_id: 90000001, character_name: 'Kesra Lund', system: 'Amamake', last_at: '2026-10-17T17:40:00Z',
    kills: 2, losses: 0, complexes: 1, advantage_sites: 0, in_fleet: true, ...extra,
})
const OVERLAY = {
    campaign: {
        slug: 'op-hekate', name: 'Operation Hekate', week_index: 2, week_count: 6, active_window_minutes: 60,
        systems: [system(), system({ system_id: 2, name: 'Huola', holder: 'amarr', change_week: -3.2 }), system({ system_id: 3, name: 'Siseide', flipped: 'captured' })],
        active_pilots: [pilot(), pilot({ character_id: 90000002, character_name: 'Ardo "<b>" Kesh', kills: 0, in_fleet: false })],
    },
}

async function campaign(payload = OVERLAY) {
    return load_campaign({ campaign_overlay: async () => payload }, 'https://my.minmatar.org')
}

test('a live campaign: one row per system and the active pilots', async () => {
    const html = content({ campaign: await campaign(), campaign_updated_at: '2026-10-17T18:00:00Z' })
    assert.equal((html.match(/class="system"/g) || []).length, 3)
    assert.match(html, /Week 2 of 6/)
    assert.match(html, /2 pilots/)
    assert.match(html, /aria-label="Amamake, Hold the complexes, gaining \+8% this week"/)
    assert.match(html, /aria-label="Huola, Hold the complexes, losing -3% this week"/)
    assert.match(html, /aria-label="Siseide, Hold the complexes, captured this week"/)
    assert.match(html, /src="https:\/\/images\.evetech\.net\/characters\/90000001\/portrait\?size=64"/)
    assert.ok(!html.includes('<b>'), 'pilot names are escaped')
    assert.match(html, /Ardo &quot;&lt;b&gt;&quot; Kesh/)
})

test('the bar carries its geometry in data attributes (no inline styles under the CSP)', async () => {
    const [amamake] = (await campaign()).systems
    const html = render_system(amamake)
    assert.ok(!/style=/.test(html))
    assert.match(html, /meter__fill" data-left="0" data-width="33.6"/)
    assert.match(html, /meter__delta meter__delta--up" data-left="33.6" data-width="8\.\d+"/)
})

test('loading, no campaign, and an error above the last good data', async () => {
    assert.match(content({ campaign: null, campaign_error: null, campaign_updated_at: null }), /skeleton/)
    assert.match(content({ campaign: null, campaign_error: null, campaign_updated_at: '2026-10-17T18:00:00Z' }), /No campaign is live right now/)
    const failed = content({ campaign: null, campaign_error: 'Could not reach <Minmatar Fleet>', campaign_updated_at: null })
    assert.equal(failed, '<p class="eve-error">Could not reach &lt;Minmatar Fleet&gt;</p>')
    const stale = content({ campaign: await campaign(), campaign_error: 'Retrying…', campaign_updated_at: '2026-10-17T18:00:00Z' })
    assert.ok(stale.startsWith('<p class="eve-error">Retrying…</p>'))
    assert.match(stale, /Amamake/)
})

test('nobody active in the last hour', async () => {
    const quiet = await campaign({ campaign: { ...OVERLAY.campaign, active_pilots: [] } })
    assert.match(render_pilots(quiet), /Nobody has flown this campaign in the last hour/)
})

const STRUCTURE = {
    id: 7, slug: 'forward-push', name: 'Structure campaign', status: 'active',
    features: { weekly_progress_enabled: false, structures_enabled: true, timers_enabled: true },
    totals: { structures_destroyed: 2, isk_destroyed: 41_600_000_000, ships_killed: 212 },
    next_timers: [
        { name: 'Blaster', type_name: 'Astrahus', system: 'Jita', stage: 3, final: true, at: '2026-10-17T19:09:00Z' },
        { name: 'Home Station', type_name: 'Fortizar', system: 'Amamake', stage: 2, final: false, at: '2026-10-17T20:02:00Z' },
    ],
}
const WARZONE = { id: 1, slug: 'op-hekate', name: 'Warzone', status: 'paused', features: { weekly_progress_enabled: true }, totals: { structures_destroyed: 0, isk_destroyed: 0, ships_killed: 0 }, next_timers: [] }
const NOW = new Date('2026-10-17T14:00:00Z')

test('a structure campaign: switcher, Totals and Next timers with stage chevrons', async () => {
    const model = await campaign({ ...OVERLAY, campaigns: [STRUCTURE, WARZONE] })
    const html = content({ campaign: model, campaign_updated_at: 'x' }, 'forward-push', NOW)
    assert.match(html, /data-campaign="forward-push" aria-pressed="true"/)
    assert.match(html, /Warzone <span class="eve-dim">&middot; paused<\/span>/)
    assert.match(html, /<span class="total__value">2<\/span><span class="total__label">Structures<\/span>/)
    assert.match(html, /41\.6B/)
    assert.match(html, />212</)
    assert.ok(!/class="system"/.test(html), 'no weekly rows when weekly progress is off')
    assert.equal((html.match(/class="timer"/g) || []).length, 2)
    assert.match(html, /stage stage--final" title="Final timer: the structure dies"/)
    assert.match(html, /title="Armor timer: a hull timer follows"/)
    assert.match(html, /Astrahus &middot;|Astrahus \u00b7 Jita/)
    assert.match(html, /data-at="2026-10-17T19:09:00Z">05:09:00</)
    assert.match(html, /Sat 19:09/)
    assert.equal((html.match(/stage__step is-on/g) || []).length, 5, 'three chevrons for stage 3, two for stage 2')
})

test('switching to the legacy campaign shows the weekly rows again', async () => {
    const model = await campaign({ ...OVERLAY, campaigns: [STRUCTURE, WARZONE] })
    const html = content({ campaign: model, campaign_updated_at: 'x' }, 'op-hekate', NOW)
    assert.equal((html.match(/class="system"/g) || []).length, 3)
    assert.match(html, /data-campaign="op-hekate" aria-pressed="true"/)
    assert.equal(selected_campaign(model, 'nope').slug, 'op-hekate', 'an unknown pick falls back to the legacy campaign')
})

test('an older backend without `campaigns` keeps today\'s window: no switcher', async () => {
    const model = await campaign()
    assert.deepEqual(model.campaigns, [])
    const html = content({ campaign: model, campaign_updated_at: 'x' })
    assert.ok(!html.includes('switcher'))
    assert.equal((html.match(/class="system"/g) || []).length, 3)
})

test('only structure campaigns live (no legacy campaign) still draws, and junk fields are ignored', async () => {
    const junk = { ...STRUCTURE, totals: { structures_destroyed: 'x' }, next_timers: [{ name: 'bad', at: 'nope' }, { ...STRUCTURE.next_timers[0], stage: 9 }] }
    const model = await campaign({ campaign: null, campaigns: [junk, { name: 'no slug' }] })
    assert.equal(model.campaigns.length, 1)
    const html = content({ campaign: model, campaign_updated_at: 'x' }, null, NOW)
    assert.ok(!html.includes('switcher'), 'one campaign needs no switcher')
    assert.match(html, /<span class="total__value">-<\/span>/)
    assert.equal((html.match(/class="timer"/g) || []).length, 1)
    assert.match(html, /stage__step is-on/)
    assert.equal(await campaign({ campaign: null, campaigns: [] }), null)
})
