import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { describe, expect, test } from 'vitest'
import RankingReel from '@components/blocks/RankingReel.astro'
import {
    fleet_commanders_reel,
    industry_manufacturers_reel,
    market_operators_reel,
    space_truckers_reel,
} from '@helpers/ranking_reels'
import { useTranslatedPath, useTranslations } from '@i18n/utils'

const t = useTranslations('en')
const translate_path = useTranslatedPath('en')
const pilot = (i: number) => ({ primary_character_id: 1000 + i, primary_character_name: `Pilot ${i}` })
const fcs = (n: number) => Array.from({ length: n }, (_, i) => ({ ...pilot(i), fleet_count: i + 1 })) as any

async function render(props: any) {
    const container = await AstroContainer.create()
    return container.renderToString(RankingReel, { props })
}

describe('ranking reel builders', () => {
    test('format each leaderboard stat the way its hub did', () => {
        expect(fleet_commanders_reel(fcs(2), t).items.map(i => i.stat_text)).toEqual(['1 fleet', '2 fleets'])
        expect(space_truckers_reel([{ ...pilot(0), completed_contracts_count: 1 }] as any, t, translate_path).items[0].stat_text).toBe('1 contract')
        expect(industry_manufacturers_reel([{ ...pilot(0), delivered_isk_estimate: '4560000' }] as any, t, translate_path).items[0].stat_text).toBe('4.56M ISK')
        expect(market_operators_reel([{ ...pilot(0), total_isk_on_market: 7_890_000_000 }] as any, t, translate_path).items[0].stat_text).toBe('7.9B ISK on market')
    })

    test('fall back for operators without a primary character', () => {
        const [item] = market_operators_reel([{ primary_character_id: null, primary_character_name: null, total_isk_on_market: 0 }] as any, t, translate_path).items
        expect(item.character_id).toBe(0)
        expect(item.character_name).toBe('')
    })

    test('only the fleet commander reel has no call to action', () => {
        expect(fleet_commanders_reel([], t).cta).toBeUndefined()
        expect(space_truckers_reel([], t, translate_path).cta?.href).toBe('/alliance/tribes/?tribe=supply')
        expect(market_operators_reel([], t, translate_path).cta?.href).toBe('/alliance/tribes/?tribe=market')
    })
})

describe('RankingReel', () => {
    test('three pilots sit in a static row that announces itself', async () => {
        const html = await render(fleet_commanders_reel(fcs(3), t))
        expect(html).not.toContain('marquee-container')
        expect(html).toContain(`x-init="$dispatch('marquee-started')"`)
        expect(html.match(/<h2[^>]*>\d<\/h2>/g)).toHaveLength(3)
    })

    test('four or more pilots scroll in a marquee', async () => {
        const html = await render(fleet_commanders_reel(fcs(5), t))
        expect(html).toContain('marquee-container')
        expect(html).toContain('Pilot 4')
    })

    test('renders the call to action after the pilots', async () => {
        const html = await render(space_truckers_reel([{ ...pilot(0), completed_contracts_count: 3 }] as any, t, translate_path))
        expect(html).toContain('flex-inline-siblings')
        expect(html.indexOf('Pilot 0')).toBeLessThan(html.indexOf(t('become_a_trucker')))
    })
})
