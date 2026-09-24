import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'

import AmamakeMarketSoldTypes from '@components/blocks/amamake-market/AmamakeMarketSoldTypes.astro'
import { get_latest_issue, resolve_sold_types } from '@/data/amamake-market'

test('AmamakeMarketSoldTypes defaults to the overall top types', async () => {
    const container = await AstroContainer.create()
    const issue = get_latest_issue()
    const result = await container.renderToString(AmamakeMarketSoldTypes, {
        props: { issue },
    })

    expect(result).toContain('hx-get')
    expect(result).toContain('amamake_market_sold_types_component')
    expect(result).toContain('sold_class=all')
    expect(result).toContain('sold_class=ships')
    expect(result).toContain(issue.top_types.rows[0]!.name)
    expect(result).toContain('aria-pressed="true"')
    const lead = issue.top_types.rows[0]!
    if (lead.markup_pct === null) {
        expect(result).toContain('—')
    } else {
        expect(result).toContain('vs Jita')
        expect(result).toContain(lead.markup_pct > 0 ? '+' : '')
    }
})

test('AmamakeMarketSoldTypes PLEX adjacent chip lists injectors and extractors', async () => {
    const container = await AstroContainer.create()
    const issue = get_latest_issue()
    const plex = resolve_sold_types(issue, 'plex-adjacent')
    const result = await container.renderToString(AmamakeMarketSoldTypes, {
        props: { issue, sold_class: 'plex-adjacent' },
    })

    expect(plex.rows.map((row) => row.name)).toEqual(
        expect.arrayContaining(['Large Skill Injector', 'Small Skill Injector', 'Skill Extractor']),
    )
    expect(result).toContain('PLEX adjacent')
    expect(result).toContain('Large Skill Injector')
    expect(result).toContain('Skill Extractor')
    expect(result).not.toContain('sold_class=blueprints')
    expect(plex.rows.every((row) => result.includes(row.name))).toBe(true)
})

test('AmamakeMarketSoldTypes ships chip lists that class top ten', async () => {
    const container = await AstroContainer.create()
    const issue = get_latest_issue()
    const ships = resolve_sold_types(issue, 'ships')
    const result = await container.renderToString(AmamakeMarketSoldTypes, {
        props: { issue, sold_class: 'ships' },
    })

    expect(ships.rows[0]).toBeDefined()
    expect(result).toContain(ships.rows[0]!.name)
    expect(result).toContain('aria-pressed="true"')
    expect(ships.rows.every((row) => result.includes(row.name))).toBe(true)
})
