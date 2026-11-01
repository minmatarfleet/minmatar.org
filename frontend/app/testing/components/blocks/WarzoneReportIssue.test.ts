import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'

import WarzoneReportIssue from '@components/blocks/warzone/WarzoneReportIssue.astro'
import { get_issue, get_latest_issue } from '@/data/warzone'

test('WarzoneReportIssue renders the latest issue sections', async () => {
    const container = await AstroContainer.create()
    const issue = get_latest_issue()
    const result = await container.renderToString(WarzoneReportIssue, {
        props: { issue },
    })

    expect(result).toContain('Scoreboard')
    expect(result).toContain('Active pilots')
    expect(result).toContain('Focus of the month')
    expect(result).toContain('Amamake')
    expect(result).toContain(issue.focus.title)
    expect(result).toContain('Where the ships died')
    expect(result).toContain('Ships lost by side')
    expect(result).toContain('About the numbers')
    expect(result).toContain('Previous owner')
    expect(result).toContain('Top ships')
})

test('group rows show month-over-month ticks on every metric', async () => {
    const container = await AstroContainer.create()
    const issue = get_latest_issue()
    const result = await container.renderToString(WarzoneReportIssue, {
        props: { issue },
    })

    const groups = result.slice(result.indexOf('id="groups"'))
    expect(groups.startsWith('id="groups"')).toBe(true)

    const row = (id: number, next_id: number) => {
        const marker = `/alliance/${id}/`
        const start = groups.indexOf(marker)
        const end = groups.indexOf(`/alliance/${next_id}/`, start + marker.length)
        expect(start).toBeGreaterThan(-1)
        expect(end).toBeGreaterThan(start)
        return groups.slice(start, end)
    }

    const [first, second, third, , , sixth] = issue.groups.rows
    const fleet = row(first.id, second.id)
    expect(fleet).toContain('title="Down 26% vs September"')
    expect(fleet).toContain('▼26%')
    expect(fleet).toContain('title="Down 27% vs September"')
    expect(fleet).toContain('▼27%')
    expect(fleet).toContain('title="Down 11% vs September"')
    expect(fleet).toContain('▼11%')
    expect(fleet).toContain('title="Down 4 percentage points vs September"')
    expect(fleet).toContain('▼4%')

    const slide = row(second.id, third.id)
    expect(slide).toContain('title="Up 28% vs September"')
    expect(slide).toContain('▲28%')
    expect(slide).toContain('title="Down 34% vs September"')
    expect(slide).toContain('▼34%')
    expect(slide).toContain('title="Up 5% vs September"')
    expect(slide).toContain('▲5%')
    expect(slide).toContain('title="Up 1 percentage point vs September"')

    const local = row(sixth.id, issue.groups.rows[6].id)
    expect(local).toContain('▲39%')
    expect(local).not.toContain('percentage points')

    const july = get_issue('yc128-07')!
    const july_html = await container.renderToString(WarzoneReportIssue, {
        props: { issue: july },
    })
    const july_groups = july_html.slice(july_html.indexOf('id="groups"'))
    const july_row = july_groups.slice(
        july_groups.indexOf(`/alliance/${july.groups.rows[0].id}/`),
        july_groups.indexOf(`/alliance/${july.groups.rows[1].id}/`),
    )
    expect(july_row).toContain('▲31%')
    expect(july_row).not.toContain('percentage points')
})
