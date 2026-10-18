// The Campaigns window's HTML, fed from a GET /api/campaigns/overlay payload through api.js load_campaign,
// the same path the window's data takes.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { load_campaign } = require('../src/main/api')
const { content, render_system, render_pilots } = require('../src/renderer/campaign_view')

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
