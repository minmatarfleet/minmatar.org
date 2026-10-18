import { readFileSync } from 'node:fs'
import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { describe, expect, test } from 'vitest'
import FleetFights from '@components/blocks/FleetFights.astro'
import FleetFightsEdit from '@components/blocks/FleetFightsEdit.astro'
import FleetRoundReport from '@components/blocks/FleetRoundReport.astro'

const contract = (name: string) =>
    JSON.parse(readFileSync(`testing/contracts/${name}.json`, 'utf8'))

async function render(component: any, props: Record<string, unknown>) {
    const container = await AstroContainer.create()
    return container.renderToString(component, { props })
}

describe('FleetFights', () => {
    test('a finished fleet lists every round with its battle report links', async () => {
        const fights = contract('fleet_fights_finished')
        const html = await render(FleetFights, { fights, fleet_id: 501 })
        expect(html).not.toContain('hx-trigger="every 30s"')
        expect(html.match(/class="\[ fight-round \]/g)).toHaveLength(2)
        expect(html).toContain('/fleets/history/501/rounds/1')
        expect(html).toContain('https://zkillboard.com/related/')
        expect(html).toContain('https://br.evetools.org/related/')
        // A pilot, not a manager: no edit button.
        expect(html).not.toContain('fleet_fights_edit_component')
    })

    test('a live fleet leads with the round being fought and refreshes itself', async () => {
        const fights = contract('fleet_fights_live')
        const html = await render(FleetFights, { fights, fleet_id: 501 })
        expect(html).toContain('hx-trigger="every 30s"')
        expect(html).toContain('fleet-fights__now--fighting')
        expect(html).toContain('Round 2')
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

describe('FleetRoundReport', () => {
    test('shows both sides and the outside battle reports', async () => {
        const fights = contract('fleet_fights_finished')
        const html = await render(FleetRoundReport, { fights, round: fights.rounds[0], position: 1, fleet_id: 501 })
        expect(html).toContain('Both sides')
        expect(html).toContain('Hostile Alliance')
        expect(html).toContain('/fleets/history/501/rounds/2')
    })
})
