import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'
import FleetSchedule from '@components/blocks/FleetSchedule.astro'
import type { FleetSchedule as FleetScheduleData } from '@helpers/fetching/fleet_schedule'

const in_hours = (h:number) => new Date(Date.now() + h * 3_600_000).toISOString()

const fleet = (id:number, location:string) => ({
    id,
    type: 'non_strategic',
    status: 'pending',
    start_time: in_hours(id + 24),
    location,
    fleet_commander_id: 1,
    fleet_commander_name: 'FC',
    description: 'Roam',
    doctrine_id: null,
}) as unknown as FleetScheduleData['fleets'][number]

function schedule(locations:FleetScheduleData['locations']):FleetScheduleData {
    const fleets = [fleet(1, 'Home - Station'), fleet(2, 'Home - Station'), fleet(3, 'Forward - Outpost')]
    return {
        fleets,
        live: [],
        next: fleets[0],
        rest: fleets.slice(1),
        doctrines: {},
        next_signups: 0,
        fc_metrics: [],
        host_filter: 'all',
        host_counts: { all: 3, alliance: 3, tribe: 0 },
        locations,
    } as FleetScheduleData
}

test('a location filter shows when the fleets form up in several places', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(FleetSchedule, {
        props: { schedule: schedule([
            { name: 'Home - Station', label: 'Home Station' },
            { name: 'Forward - Outpost', label: 'Forward' },
        ]) },
    })
    expect(html).toContain('Filter fleets by form-up location')
    expect(html).toContain('x-on:click="fleet_location = 1"')
    expect(html).toMatch(/data-tippy-content="Forward - Outpost"[^>]*>\s*Forward\s*<\/button>/)
})

test('no location filter for a single form-up location', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(FleetSchedule, { props: { schedule: schedule([]) } })
    expect(html).not.toContain('Filter fleets by form-up location')
    expect(html).not.toContain('fleet_location ===')
})
