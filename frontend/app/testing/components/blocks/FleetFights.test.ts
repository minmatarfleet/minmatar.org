import { readFileSync } from 'node:fs'
import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { describe, expect, test } from 'vitest'
import FleetFights from '@components/blocks/FleetFights.astro'
import FleetFightsEdit from '@components/blocks/FleetFightsEdit.astro'
import FleetBattleReport from '@components/blocks/FleetBattleReport.astro'

const contract = (name: string) =>
    JSON.parse(readFileSync(`testing/contracts/${name}.json`, 'utf8'))

async function render(component: any, props: Record<string, unknown>) {
    const container = await AstroContainer.create()
    return container.renderToString(component, { props })
}

describe('FleetFights', () => {
    test('a finished fleet lists every engagement with a link to its battle report', async () => {
        const fights = contract('fleet_fights_finished')
        const html = await render(FleetFights, { fights, fleet_id: 501 })
        expect(html).not.toContain('hx-trigger="every 30s"')
        expect(html.match(/class="\[ fight-round \]/g)).toHaveLength(2)
        // Each engagement opens the fleet's report at its window.
        expect(html).toContain('/fleets/history/501/report?start=')
        expect(html).toContain('href="/fleets/history/501/report"')
        // Outside tools cover the whole fleet only, never one engagement.
        expect(html).not.toContain('https://zkillboard.com/related/')
        expect(html).not.toContain('https://br.evetools.org/related/')
        // No stat strip and no footnote explaining the rules.
        expect(html).not.toContain('fleet-fights__totals')
        expect(html).not.toContain('quiet minutes')
        // A pilot, not a manager: no edit button.
        expect(html).not.toContain('fleet_fights_edit_component')
    })

    test('a live fleet leads with the round being fought and refreshes itself', async () => {
        const fights = contract('fleet_fights_live')
        const html = await render(FleetFights, { fights, fleet_id: 501 })
        expect(html).toContain('hx-trigger="every 30s"')
        expect(html).toContain('fleet-fights__now--fighting')
        expect(html).toContain('Engagement 2')
        // The FC can fix the rounds.
        expect(html).toContain('fleet_fights_edit_component')
    })

    test('a fleet still building asks again shortly', async () => {
        const html = await render(FleetFights, { fights: { fleet_id: 501, status: 'building', live: false, rounds: [], events: [], edits: [] }, fleet_id: 501 })
        expect(html).toContain('hx-trigger="load delay:5s"')
    })
})

describe('FleetFightsEdit', () => {
    test('offers a checkbox per round and the split points inside it', async () => {
        const fights = contract('fleet_fights_live')
        const html = await render(FleetFightsEdit, { fights, fleet_id: 501 })
        expect(html.match(/name="segment"/g)).toHaveLength(fights.rounds.length)
        expect(html).toContain('value="merge"')
    })
})

const team = (index: number, ours: boolean, pilots: any[], groups: any[], totals: Record<string, number>) => ({
    index, ours, pilots, groups,
    totals: { pilots: pilots.length, damage: 0, ships_lost: 0, pods_lost: 0, isk_lost: 0, isk_destroyed: 0, efficiency: 0, ...totals },
})

const pilot = (character_id: number, name: string, alliance_id: number, ship: any, extra: Record<string, number> = {}) => ({
    character_id, name, corporation_id: 98000000 + character_id, corporation_name: `${name} Corp`,
    alliance_id, alliance_name: `${name} Alliance`, group_id: alliance_id, ships: [ship], kills: 0, damage: 0, ...extra,
})

const battle_report = (fights: any, overrides: Record<string, unknown> = {}) => ({
    fleet_id: 501, whole: true,
    window_start: '2026-01-17T17:38:00Z', window_end: '2026-01-17T18:01:00Z',
    start: fights.rounds[0].start, end: fights.rounds[1].end, minutes: 19,
    span_start: '2026-01-17T17:38:00Z', span_end: '2026-01-17T18:01:00Z',
    systems: [{ id: 30002537, name: 'Amamake' }], complete: true, sides: '',
    teams: [
        team(0, true,
            [pilot(1001, 'Pilot One', 99011978, { type_id: 11987, name: 'Guardian', lost: true, killmail_id: 7001 })],
            [{ id: 99011978, kind: 'alliance', name: 'Minmatar Fleet Alliance', pilots: 1, ships_lost: 1, isk_lost: 250000000 }],
            { ships_lost: 1, isk_lost: 250000000 }),
        team(1, false,
            [pilot(2001, 'Hostile One', 1988009451, { type_id: 587, name: 'Rifter', lost: false, killmail_id: null }, { kills: 1, damage: 1200 })],
            [{ id: 1988009451, kind: 'alliance', name: 'Hostile Alliance', pilots: 1, ships_lost: 0, isk_lost: 0 }],
            { damage: 1200, isk_destroyed: 250000000, efficiency: 100 }),
    ],
    killmails: [{ id: 7001, time: fights.rounds[0].start, system_id: 30002537, system_name: 'Amamake', ship_type_id: 11987, ship_name: 'Guardian',
        victim_id: 1001, victim_name: 'Pilot One', victim_corporation_id: 98001001, victim_alliance_id: 99011978, victim_group_id: 99011978,
        team: 0, isk: 250000000, pod: false, attackers: 1, final_blow: { character_id: 2001, name: 'Hostile One', ship_type_id: 587 } }],
    activity: [
        { minute: '2026-01-17T17:40:00Z', isk: [250000000, 0, 0] },
        { minute: '2026-01-17T17:57:00Z', isk: [0, 60000000, 0] },
    ],
    fights: fights.rounds.map((round: any) => ({ start: round.start, end: round.end })),
    segments: [{ id: 9, name: 'Opening brawl', start: '2026-01-17T17:39:00Z', end: '2026-01-17T17:44:00Z' }],
    segment_id: null,
    can_edit_segments: false,
    ...overrides,
})

const props = (fights: any, overrides: Record<string, unknown> = {}) =>
    ({ report: battle_report(fights, overrides), fleet_id: 501, back_href: '/fleets/history/501#aar' })

describe('FleetBattleReport', () => {
    test('opens on the whole fleet: activity strip, team cards with « » moves and the five views', async () => {
        const fights = contract('fleet_fights_finished')
        const html = await render(FleetBattleReport, props(fights))
        expect(html).toContain('Whole fleet')
        expect(html.match(/class="\[ br__bar \]/g)).toHaveLength(2)
        expect(html).toContain('Team A')
        expect(html).toContain('Team B')
        for (const view of ['Involved', 'Summary', 'Timeline', 'Damage', 'Composition'])
            expect(html).toContain(`>${view}</button>`)
        // Team A moves right; Team B moves left or opens Team C.
        expect(html.match(/class="\[ br__move \]/g)).toHaveLength(3)
        expect(html).toContain('fleet_battle_report_component')
        // An alliance from before 2010 still gets its alliance logo.
        expect(html).toContain('images.evetech.net/alliances/1988009451/logo')
        expect(html).toContain('https://zkillboard.com/kill/7001/')
        expect(html).toContain('final blow Hostile One')
        // The FC's segment is a chip anyone can open.
        expect(html).toContain('/fleets/history/501/report?segment=9')
    })

    test('a pilot looking at a window can share it but not save or delete segments', async () => {
        const fights = contract('fleet_fights_finished')
        const html = await render(FleetBattleReport, props(fights, { whole: false, window_start: '2026-01-17T17:39:00Z', window_end: '2026-01-17T17:44:00Z' }))
        expect(html).toContain('17:39–17:44 ET')
        expect(html).toContain('class="[ br__sel ]')
        expect(html).not.toContain('name="action" value="save"')
        expect(html).not.toContain('name="action" value="delete"')
    })

    test('the FC saves a window as a segment and can delete segments', async () => {
        const fights = contract('fleet_fights_finished')
        const html = await render(FleetBattleReport, props(fights, { whole: false, can_edit_segments: true }))
        expect(html).toContain('name="action" value="save"')
        expect(html).toContain('aria-label="Delete segment Opening brawl"')
    })

    test('a third party of three pilots or fewer gets a band, not a column', async () => {
        const fights = contract('fleet_fights_finished')
        const report = battle_report(fights)
        const third = team(2, false,
            [pilot(3001, 'Third One', 99000800, { type_id: 16242, name: 'Thrasher', lost: false, killmail_id: null })],
            [{ id: 99000800, kind: 'alliance', name: 'Third Alliance', pilots: 1, ships_lost: 0, isk_lost: 0 }], {})
        const html = await render(FleetBattleReport, { ...props(fights), report: { ...report, teams: [...report.teams, third] } })
        expect(html).toContain('br__band')
        expect(html).toContain('third party')
        expect(html).toContain('grid-template-columns: repeat(2, minmax(0, 1fr))')
    })
})
