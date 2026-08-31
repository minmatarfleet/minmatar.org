import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'
import AmamakeMarketReport from '@components/blocks/campaigns/amamake-market/AmamakeMarketReport.astro'

test('AmamakeMarketReport renders standing sections and August focus', async () => {
    const container = await AstroContainer.create()
    const result = await container.renderToString(AmamakeMarketReport, {})

    expect(result).toContain('The month')
    expect(result).toContain('Focus of the month')
    expect(result).toContain('Kamela')
    expect(result).toContain('Import vs local')
    expect(result).toContain('amamake-week-isk')
    expect(result).not.toContain('/alliance/campaigns/amamake-market')
})
