import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { describe, expect, test } from 'vitest'
import StagingInfo from '@components/blocks/StagingInfo.astro'
import { STAGINGS, STAGING_SWITCHER_OPTIONS, known_staging } from '@/data/stagings'
import { stagings } from '@dtypes/layout_components'

async function render(props: Record<string, unknown>) {
    const container = await AstroContainer.create()
    return container.renderToString(StagingInfo, { props })
}

function switcher_tags(html: string) {
    return [...html.matchAll(/set_staging\?tag=([a-z_]+)/g)].map(match => match[1])
}

describe('STAGINGS', () => {
    test('has a row for every staging slug', () => {
        expect(Object.keys(STAGINGS).sort()).toEqual([...stagings].sort())
    })

    test('switcher lists the pickable stagings, then Random', () => {
        expect(STAGING_SWITCHER_OPTIONS.map(option => option.slug)).toEqual(['amamake', 'watermellon', 'random'])
    })

    test('unknown values fall back to Sosala', () => {
        expect(known_staging('amarr')).toBe('amarr')
        expect(known_staging('auga')).toBe('watermellon')
        expect(known_staging('')).toBe('watermellon')
    })
})

describe('StagingInfo', () => {
    test.each([
        ['amamake', 'Amamake', 'Hed', 'Heimatar', 'Amamake - 5 times nearly AT winners'],
        ['watermellon', 'Sosala', 'Vaarma', 'The Bleak Lands', 'Sosala – WATERMELON'],
        ['amarr', 'Amarr', 'Throne Worlds', 'Domain', 'Amarr VIII (Oris) - Emperor Family Academy'],
    ])('renders the %s card', async (slug, system, constellation, region, station_name) => {
        const html = await render({ slug })
        expect(html).toContain(`${system} <span`)
        expect(html).toContain(constellation)
        expect(html).toContain(region)
        expect(html).toContain(station_name)
    })

    test('a picked staging is left out of its own switcher', async () => {
        expect(switcher_tags(await render({ slug: 'amamake' }))).toEqual(['watermellon', 'random'])
        expect(switcher_tags(await render({ slug: 'watermellon' }))).toEqual(['amamake', 'random'])
    })

    test('a random staging offers the real stagings, not Random', async () => {
        expect(switcher_tags(await render({ slug: 'amamake', is_random: true }))).toEqual(['amamake', 'watermellon'])
    })

    test('Amarr has no switcher', async () => {
        expect(switcher_tags(await render({ slug: 'amarr' }))).toEqual([])
    })

    test('unknown slugs render Sosala', async () => {
        expect(await render({ slug: 'auga' })).toContain('Sosala – WATERMELON')
    })
})
