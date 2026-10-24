import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'

import ShipTargetMeter from '@components/blocks/ShipTargetMeter.astro'
import FleetShipTargets from '@components/blocks/FleetShipTargets.astro'

const render = async (props:{ name:string, have:number, target:number, compact?:boolean }) => {
    const container = await AstroContainer.create()
    return await container.renderToString(ShipTargetMeter, { props })
}

test('a short line says how many more are needed', async () => {
    const html = await render({ name: 'Dreads', have: 14, target: 40 })
    expect(html).toContain('26 needed')
    expect(html).toContain('14 of 40')
    expect(html).not.toContain('is-met')
})

test('a full line says Met, and how many extra', async () => {
    expect(await render({ name: 'FAX', have: 4, target: 4 })).toContain('✓ Met')
    expect(await render({ name: 'Dreads', have: 44, target: 40 })).toContain('✓ Met · 4 extra')
})

test('compact meters leave out the counts', async () => {
    const html = await render({ name: 'TFIs', have: 8, target: 40, compact: true })
    expect(html).toContain('32 needed')
    expect(html).not.toContain('ship-target-meter__counts')
})

const line = (id:number, name:string, have:number, target:number) =>
    ({ id, name, have, target, short: Math.max(target - have, 0), ship_type_ids: [], group_ids: [] })

test('Find pilots shows only on short lines of a private fleet', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(FleetShipTargets, {
        props: {
            fleet_id: 1,
            targets: [line(1, 'Logistics', 6, 20), line(2, 'FAX', 4, 4)],
            can_manage: true,
            can_invite: true,
        },
    })
    expect(html.match(/mode=find/g)?.length).toBe(1)
    expect(html).toContain('10 of 24 signed up')
})

test('pilots see the lines without actions', async () => {
    const container = await AstroContainer.create()
    const html = await container.renderToString(FleetShipTargets, {
        props: { fleet_id: 1, targets: [line(1, 'Logistics', 6, 20)], can_manage: false, can_invite: false },
    })
    expect(html).toContain('14 needed')
    expect(html).not.toContain('mode=edit')
})
