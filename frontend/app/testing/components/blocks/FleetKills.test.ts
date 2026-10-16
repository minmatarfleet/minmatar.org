import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'

import FleetKills from '@components/blocks/FleetKills.astro'
import type { FleetKillmail, FleetKills as FleetKillsData } from '@helpers/api.minmatar.org/fleets'

const killmail = (overrides:Partial<FleetKillmail>):FleetKillmail => ({
    killmail_id: 139189498,
    killmail_time: '2026-10-16T00:09:17+00:00',
    outcome: 'kill',
    solar_system_id: 30002097,
    solar_system_name: 'Klogori',
    victim_ship_type_id: 28665,
    victim_ship_name: 'Vargur',
    victim_character_id: 1,
    victim_character_name: 'PuwPuw',
    isk_value: 2_197_437_282,
    fleet_pilots: 9,
    is_capsule: false,
    ...overrides,
})

const fleet_kills = (overrides:Partial<FleetKillsData> = {}):FleetKillsData => ({
    fleet_id: 2393,
    tracked: true,
    isk_destroyed: 2_229_925_142,
    isk_lost: 74_454_802,
    ships_destroyed: 1,
    pods_destroyed: 1,
    ships_lost: 1,
    pods_lost: 0,
    killmails: [
        killmail({}),
        killmail({ killmail_id: 2, victim_ship_type_id: 670, victim_ship_name: 'Capsule', isk_value: 32_487_860, is_capsule: true }),
        killmail({ killmail_id: 3, outcome: 'loss', victim_ship_name: 'Omen Navy Issue', victim_character_name: 'BearThatCares' }),
    ],
    ...overrides,
})

test('FleetKills shows totals and only the kills', async () => {
    const container = await AstroContainer.create()
    const result = await container.renderToString(FleetKills, {
        props: { fleet_kills: fleet_kills() },
    })

    expect(result).toContain('ISK destroyed')
    expect(result).toContain('2.2B')
    expect(result).toContain('Ships destroyed')
    expect(result).toContain('+1 pods')
    expect(result).toContain('ISK lost')
    expect(result).toContain('Vargur')
    expect(result).toContain('flown by PuwPuw')
    expect(result).toContain('https://zkillboard.com/kill/139189498/')
    expect(result).toContain('Klogori')
    expect(result).not.toContain('Omen Navy Issue')
})

test('FleetKills says so when nothing died', async () => {
    const container = await AstroContainer.create()
    const result = await container.renderToString(FleetKills, {
        props: { fleet_kills: fleet_kills({ killmails: [], isk_destroyed: 0, ships_destroyed: 0, pods_destroyed: 0 }) },
    })

    expect(result).toContain('No kills recorded for this fleet.')
    expect(result).not.toContain('role="table"')
})

test('FleetKills explains an untracked fleet', async () => {
    const container = await AstroContainer.create()
    const result = await container.renderToString(FleetKills, {
        props: { fleet_kills: fleet_kills({ tracked: false, killmails: [] }) },
    })

    expect(result).toContain('This fleet was not tracked')
    expect(result).not.toContain('ISK destroyed')
})
