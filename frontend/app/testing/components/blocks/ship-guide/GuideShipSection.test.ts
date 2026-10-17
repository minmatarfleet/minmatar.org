import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { describe, expect, test } from 'vitest'
import GuideShipSection from '@components/blocks/ship-guide/GuideShipSection.astro'
import GuideMatchupChart from '@components/blocks/ship-guide/GuideMatchupChart.astro'
import * as frigates from '@/data/navy-frigate-guide'
import { resolveMatchupOpponentShip as resolve_frigate } from '@/data/navy-frigate-guide/opponent-ships'
import * as cruisers from '@/data/faction-warfare-cruiser-guide'
import { resolveMatchupOpponentShip as resolve_cruiser } from '@/data/faction-warfare-cruiser-guide/opponent-ships'

const FITS_LEAD = 'Example fittings for each role above.'

async function render_ship(props: Record<string, unknown>) {
    const container = await AstroContainer.create()
    return container.renderToString(GuideShipSection, { props })
}

describe('GuideShipSection', () => {
    test('keeps the per-guide ids and hull class', async () => {
        const ship = frigates.shipGuides[0]
        const fittings = frigates.getGuideFittingsForShip(ship.id)
        const html = await render_ship({
            ship,
            fittings,
            hull_class: 'Frigate',
            id_prefix: 'nfg',
            resolve_opponent: resolve_frigate,
        })

        expect(html).toContain(`id="${ship.id}"`)
        expect(html).toContain(`${ship.faction} Frigate · ${ship.shortName}`)
        expect(html).toContain(`id="nfg-fit-${fittings[0].id}"`)
        expect(html).not.toContain('guide-ship__fits-lead')
        // Every matchup entry renders a card.
        const entries = ship.matchups.reduce((n, group) => n + group.entries.length, 0)
        expect(html.match(/class="guide-matchup-card"/g)?.length).toBe(entries)
    })

    test('renders the optional fits lead', async () => {
        const ship = cruisers.shipGuides[0]
        const html = await render_ship({
            ship,
            fittings: cruisers.getGuideFittingsForShip(ship.id),
            hull_class: 'Cruiser',
            id_prefix: 'fwc',
            resolve_opponent: resolve_cruiser,
            fits_lead: FITS_LEAD,
        })

        expect(html).toContain(`${ship.faction} Cruiser · ${ship.shortName}`)
        expect(html).toContain(FITS_LEAD)
        expect(html).toContain('id="fwc-fit-')
    })
})

describe('GuideMatchupChart', () => {
    test('labels every cell for screen readers', async () => {
        const chart = frigates.matchupCharts[0]
        const container = await AstroContainer.create()
        const html = await container.renderToString(GuideMatchupChart, { props: { chart } })

        const cells = chart.rows.length * chart.columns.length
        expect(html.match(/class="guide-chart__cell"/g)?.length).toBe(cells)
        expect(html).toContain(`${chart.rows[0]} vs ${chart.columns[0]}: `)
    })
})
