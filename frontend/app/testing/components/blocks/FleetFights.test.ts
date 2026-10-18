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
        expect(html).toContain('/fleets/history/501/rounds/1')
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

const battle_report = (fights: any) => ({
    fleet_id: 501, position: 1, kind: 'round', number: 1,
    start: fights.rounds[0].start, end: fights.rounds[0].end, minutes: 5,
    window_start: fights.rounds[0].start, window_end: fights.rounds[0].end,
    systems: [{ id: 30002537, name: 'Amamake' }], complete: true, sides: '',
    teams: [
        {
            index: 0, ours: true,
            totals: { pilots: 1, ships_lost: 1, pods_lost: 0, isk_lost: 250000000, isk_destroyed: 0, efficiency: 0 },
            groups: [{ id: 99011978, kind: 'alliance', name: 'Minmatar Fleet Alliance', pilots: 1, ships_lost: 1, isk_lost: 250000000 }],
            pilots: [{ character_id: 1001, name: 'Pilot One', corporation_id: 98000001, alliance_id: 99011978, group_id: 99011978,
                ships: [{ type_id: 11987, name: 'Guardian', lost: true, killmail_id: 7001 }], kills: 0, damage: 0 }],
        },
        {
            index: 1, ours: false,
            totals: { pilots: 1, ships_lost: 0, pods_lost: 0, isk_lost: 0, isk_destroyed: 250000000, efficiency: 100 },
            groups: [{ id: 99000002, kind: 'alliance', name: 'Hostile Alliance', pilots: 1, ships_lost: 0, isk_lost: 0 }],
            pilots: [{ character_id: 2001, name: 'Hostile One', corporation_id: 98000002, alliance_id: 99000002, group_id: 99000002,
                ships: [{ type_id: 587, name: 'Rifter', lost: false, killmail_id: null }], kills: 1, damage: 1200 }],
        },
    ],
    killmails: [{ id: 7001, time: fights.rounds[0].start, system_id: 30002537, system_name: 'Amamake', ship_type_id: 11987, ship_name: 'Guardian',
        victim_id: 1001, victim_name: 'Pilot One', victim_corporation_id: 98000001, victim_alliance_id: 99011978, victim_group_id: 99011978,
        team: 0, isk: 250000000, pod: false, attackers: 1, final_blow: { character_id: 2001, name: 'Hostile One', ship_type_id: 587 } }],
})

describe('FleetBattleReport', () => {
    test('shows a card per side with groups that can move, and every killmail', async () => {
        const fights = contract('fleet_fights_finished')
        const html = await render(FleetBattleReport, { report: battle_report(fights), fights, position: 1, fleet_id: 501 })
        expect(html).toContain('Our side')
        expect(html).toContain('Side B')
        expect(html).toContain('Hostile Alliance')
        expect(html.match(/name="team"/g)).toHaveLength(2)
        expect(html).toContain('fleet_battle_report_component')
        expect(html).toContain('https://zkillboard.com/kill/7001/')
        expect(html).toContain('/fleets/history/501/rounds/2')
        // Exact to the engagement: no outside battle report tools.
        expect(html).not.toContain('br.evetools.org')
    })
})
