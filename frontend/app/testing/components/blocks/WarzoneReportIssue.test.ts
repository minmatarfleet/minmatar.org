import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'

import WarzoneReportIssue from '@components/blocks/warzone/WarzoneReportIssue.astro'
import { get_latest_issue } from '@/data/warzone'

test('WarzoneReportIssue renders July YC128 sections', async () => {
    const container = await AstroContainer.create()
    const issue = get_latest_issue()
    const result = await container.renderToString(WarzoneReportIssue, {
        props: { issue },
    })

    expect(result).toContain('Scoreboard')
    expect(result).toContain('Active pilots')
    expect(result).toContain('Focus of the month')
    expect(result).toContain('Amamake')
    expect(result).toContain('Auga siege')
    expect(result).toContain('Where the ships died')
    expect(result).toContain('Ships lost by side')
    expect(result).toContain('About the numbers')
    expect(result).toContain('Previous owner')
})
