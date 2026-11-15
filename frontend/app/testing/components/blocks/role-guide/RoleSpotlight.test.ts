import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'
import RoleSpotlight from '@components/blocks/role-guide/RoleSpotlight.astro'

const spotlight = {
    mentors: [],
    pilots: [
        { character_id: 2, name: 'Busy Logi', fleets: 12 },
        { character_id: 3, name: 'Second Logi', fleets: 7 },
    ],
    fleets: [],
    fleets_days: 60,
    hulls: [],
}

test('Lists the pilots who fly the role most, busiest first, over 90 days', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(RoleSpotlight, { props: { spotlight } })
    expect(html).toContain('Pilots who fly it most')
    expect(html).toContain('last 90 days')
    expect(html.indexOf('Busy Logi')).toBeLessThan(html.indexOf('Second Logi'))
    expect(html).toContain('12 fleets')
})

test('Nobody in the window: says so', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(RoleSpotlight, { props: { spotlight: { ...spotlight, pilots: [] } } })
    expect(html).toContain('Nobody has flown these ships on a tracked fleet in the last 90 days.')
})

test('Logged out: asks to log in', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(RoleSpotlight, { props: { spotlight: null } })
    expect(html).toContain('Log in to see who flies it.')
})
