import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'

import AmamakeMarketReportIssue from '@components/blocks/amamake-market/AmamakeMarketReportIssue.astro'
import { get_latest_issue } from '@/data/amamake-market'

test('AmamakeMarketReportIssue renders the latest issue sections', async () => {
    const container = await AstroContainer.create()
    const issue = get_latest_issue()
    const result = await container.renderToString(AmamakeMarketReportIssue, {
        props: { issue },
    })

    expect(result).toContain('Through the book')
    expect(result).toContain('What sold')
    expect(result).toContain('Died vs sold')
    expect(result).toContain('The catchment')
    expect(result).toContain('Focus of the month')
    expect(result).toContain(issue.focus.title)
    expect(result).toContain('Import vs local')
    expect(result).toContain('Build in Amamake')
    expect(result).toContain('Loyalty points')
    expect(result).toContain('About the numbers')
    expect(result).toContain(issue.top_types.rows[0]!.name)
    expect(result).toContain(issue.sales.isk_label)
    expect(result).not.toContain('/campaigns/amamake-market')
})
