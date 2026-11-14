import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'
import RoleSpotlight from '@components/blocks/role-guide/RoleSpotlight.astro'

const spotlight = {
    mentors: [{ character_id: 1, name: 'Mentor Pilot', fleets: 9 }],
    pilots: [{ character_id: 2, name: 'Busy Logi', fleets: 12 }],
    fleets: [{ fleet_id: 7, start_time: '2026-09-19T19:00:00Z', type: 'Strategic Operation', objective: 'Enemy Fortizar Timer', doctrine: 'TFIs', pilots_in_role: 17 }],
    fleets_days: 60,
}

test('Ask names the mentors who fly the role, then the busiest pilots', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(RoleSpotlight, { props: { part: 'pilots', spotlight } })
    expect(html).toContain('Mentors who fly it')
    expect(html).toContain('Mentor Pilot')
    expect(html).toContain('Mentor · 9 fleets in the role this year')
    expect(html.indexOf('Mentor Pilot')).toBeLessThan(html.indexOf('Busy Logi'))
    expect(html).toContain('12 fleets this year')
})

test('No mentors: the section starts with the busiest pilots', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(RoleSpotlight, { props: { part: 'pilots', spotlight: { ...spotlight, mentors: [] } } })
    expect(html).not.toContain('Mentors who fly it')
    expect(html).toContain('Pilots who fly it most')
})

test('Fleets link their fleet page, and a quiet role says this year', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(RoleSpotlight, { props: { part: 'fleets', spotlight: { ...spotlight, fleets_days: 365 } } })
    expect(html).toContain('/fleets/history/7')
    expect(html).toContain('Enemy Fortizar Timer')
    expect(html).toContain('17 in the role')
    expect(html).toContain('Fleets that flew it this year')
})
