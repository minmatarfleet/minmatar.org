import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { describe, expect, test } from 'vitest'
import CampaignCoverageChart from '@components/blocks/CampaignCoverageChart.astro'

const coverage = Array.from({ length: 24 }, (_, hour) => ({ hour, our_active_days: hour % 4, hostile_activity: hour % 3 }))

async function render(props: Record<string, unknown>) {
    const container = await AstroContainer.create()
    return container.renderToString(CampaignCoverageChart, { props })
}

describe('CampaignCoverageChart', () => {
    test('hides the plot from assistive tech and gives it a data table instead', async () => {
        const html = await render({ coverage })
        expect(html).not.toContain('role="img"')
        expect(html).toMatch(/class="\[ campaign-coverage-chart \]"[^>]*aria-hidden="true"/)
        expect(html).toContain('<caption>')
        expect(html.match(/<th scope="row"/g)).toHaveLength(24)
        // 05:00 has 1 day of our activity and 2 of hostile activity.
        expect(html).toMatch(/<th scope="row"[^>]*>05:00 UTC<\/th>\s*<td[^>]*>1<\/td>\s*<td[^>]*>2<\/td>/)
    })

    test('shows the empty state without a table', async () => {
        const html = await render({ coverage: [] })
        expect(html).not.toContain('<table')
    })
})
