import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'

import FleetRoles from '@components/blocks/FleetRoles.astro'
import type { FleetCompositionEntry, FleetRoleCoverage, FleetRolePilot } from '@helpers/api.minmatar.org/fleets'

const fit = (key:string, ship_name:string, fit_roles:Partial<FleetCompositionEntry['fit_roles']>):FleetCompositionEntry => ({
    key, fitting_id: 1, fleet_fitting_id: null, name: ship_name, ship_id: 1, ship_name, ship_group: '',
    role: 'support', source: 'doctrine', eft_format: '', refits: [], module_slots: {},
    fit_roles: {
        links: false, burst_slots: 0, bursts_online: {}, bursts_fitted: {}, cyno: false, logi: false,
        interdiction: false, ecm: false, neuts: false, ...fit_roles,
    },
})

const COMPOSITION = [
    fit('f:177', 'Damnation', { links: true, burst_slots: 3, bursts_online: { skirmish: 1, information: 2 }, bursts_fitted: { armor: 3, skirmish: 2, information: 2 } }),
    fit('f:57', 'Devoter', { cyno: true }),
    fit('f:362', 'Guardian', { logi: true }),
]

const pilot = (overrides:Partial<FleetRolePilot>):FleetRolePilot => ({
    character_id: 1001, character_name: 'Pilot One', ship_id: 22474, ship_name: 'Damnation', fitting_name: '',
    source: 'volunteer', in_fleet: false, count: 0, ship_volunteer_id: 5, ...overrides,
})

const roles = (overrides:Partial<FleetRoleCoverage> = {}):FleetRoleCoverage => ({
    logi_fc: [],
    links: [
        { kind: 'armor', label: 'Armor', pilots: [] },
        { kind: 'shield', label: 'Shield', pilots: [] },
        { kind: 'skirmish', label: 'Skirmish', pilots: [pilot({ count: 1 })] },
        { kind: 'information', label: 'Information', pilots: [pilot({ count: 2 })] },
    ],
    cynos: [],
    logi: [],
    interdiction: [],
    ecm: [],
    neuts: [],
    wanted: { interdiction: 0, neuts: 0, ecm: 0 },
    ...overrides,
})

const render = async (props:Record<string, unknown>) => {
    const container = await AstroContainer.create()
    return container.renderToString(FleetRoles, {
        props: { roles: roles(), composition: COMPOSITION, pilots: [], fleet_id: 2400, ...props },
    })
}

test('links rows follow what the doctrine can run', async () => {
    const result = await render({})

    expect(result).toContain('Armor links')
    expect(result).toContain('Skirmish links')
    expect(result).toContain('Information links')
    expect(result).not.toContain('Shield links')
    expect(result).toContain('Damnation ×2')
    // Nobody runs armor yet: point at the ship that can.
    expect(result).toContain('Volunteer a Damnation')
})

test('cyno and logi rows come from ships; Logi FC stays a sign-up', async () => {
    const result = await render({
        roles: roles({
            cynos: [pilot({ character_name: 'Cyno Pilot', ship_name: 'Devoter', solar_system_name: 'Sosala' })],
            logi: [pilot({ character_name: 'Logi Pilot', ship_name: 'Guardian', source: 'in_fleet', in_fleet: true, ship_volunteer_id: null })],
        }),
    })

    expect(result).toContain('Logi FC')
    expect(result).toContain('Cyno Pilot')
    expect(result).toContain('Sosala')
    expect(result).toContain('Logi Pilot')
    expect(result).toContain('in fleet')
    // 3 link kinds + Logi FC + cynos have targets; skirmish and info are filled.
    expect(result).toContain('2/5 roles filled')
})

test('the FC can assign a cyno system; others cannot', async () => {
    const with_cyno = roles({ cynos: [pilot({ ship_name: 'Devoter' })] })

    expect(await render({ roles: with_cyno, is_fleet_commander: true })).toContain('cyno-system-5')
    expect(await render({ roles: with_cyno })).not.toContain('cyno-system-5')
})

test('a doctrine without cyno or logi ships hides those rows', async () => {
    const result = await render({ composition: [COMPOSITION[0]] })

    expect(result).not.toContain('Cynos')
    expect(result).not.toContain('>Logi<')
})

test('interdiction, neut and ECM rows come from ships; strategic fleets set targets', async () => {
    const composition = [
        ...COMPOSITION,
        fit('f:20', 'Sabre', { interdiction: true }),
        fit('f:88', 'Curse', { neuts: true }),
    ]
    const sabre = pilot({ character_name: 'Bubble Pilot', ship_name: 'Sabre' })

    const listed = await render({ composition, roles: roles({ interdiction: [sabre] }) })
    expect(listed).toContain('Interdiction')
    expect(listed).toContain('Bubble Pilot')
    expect(listed).toContain('Volunteer a Curse')
    expect(listed).toContain('id="neuts-role"')
    expect(listed).not.toContain('id="ecm-role"')
    // No targets outside strategic fleets.
    expect(listed).toContain('2/5 roles filled')

    const strategic = await render({
        composition,
        roles: roles({ interdiction: [sabre], wanted: { interdiction: 2, neuts: 2, ecm: 1 } }),
    })
    // Interdiction 1 of 2 and neuts 0 of 2 count, both short.
    expect(strategic).toContain('2/7 roles filled')
    expect(strategic).toContain('1 of 2')
})
