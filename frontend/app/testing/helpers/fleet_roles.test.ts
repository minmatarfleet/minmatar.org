import { expect, test } from 'vitest'

import type { FleetCompositionEntry, FleetRoleCoverage } from '@helpers/api.minmatar.org/fleets'
import {
    bursts_from_counts,
    bursts_summary,
    counts_from_bursts,
    link_kinds,
    ships_for_role,
} from '@helpers/fleet_roles'

const entry = (overrides:Partial<FleetCompositionEntry>):FleetCompositionEntry => ({
    key: 'f:1',
    fitting_id: 1,
    fleet_fitting_id: null,
    name: 'Fit',
    ship_id: 1,
    ship_name: 'Ship',
    ship_group: '',
    role: 'primary',
    source: 'doctrine',
    eft_format: '',
    refits: [],
    module_slots: {},
    fit_roles: { links: false, burst_slots: 0, bursts_online: {}, bursts_fitted: {}, cyno: false, logi: false },
    ...overrides,
})

const DAMNATION = entry({
    key: 'f:177',
    name: '[FL33T] 3X/4X Damnation',
    ship_name: 'Damnation',
    fit_roles: {
        links: true,
        burst_slots: 3,
        bursts_online: { skirmish: 1, information: 2 },
        bursts_fitted: { armor: 3, skirmish: 2, information: 2 },
        cyno: false,
        logi: false,
    },
})

const empty_roles = (kinds:FleetRoleCoverage['links'][number]['kind'][]):FleetRoleCoverage => ({
    logi_fc: [],
    links: kinds.map(kind => ({ kind, label: kind, pilots: [] })),
    cynos: [],
    logi: [],
})

test('burst lists and counts round-trip in canonical order', () => {
    expect(bursts_from_counts({ information: 2, skirmish: 1 })).toEqual(['skirmish', 'information', 'information'])
    expect(counts_from_bursts(['information', 'skirmish', 'information'])).toEqual({ information: 2, skirmish: 1 })
})

test('bursts_summary groups repeats', () => {
    const labels = { armor: 'Armor', shield: 'Shield', skirmish: 'Skirmish', information: 'Information', mining: 'Mining' }
    expect(bursts_summary(['skirmish', 'information', 'information'], labels)).toBe('Skirmish · Information ×2')
})

test('link rows show only kinds the doctrine can run', () => {
    const rows = link_kinds(empty_roles(['armor', 'shield', 'skirmish', 'information']), [DAMNATION])
    expect(rows.map(row => row.kind)).toEqual(['armor', 'skirmish', 'information'])
    expect(rows[0].ship_names).toEqual(['Damnation'])
})

test('a kind someone brings shows even if no doctrine fit runs it', () => {
    const roles = empty_roles(['shield'])
    roles.links[0].pilots = [{
        character_id: 1, character_name: 'P', ship_id: 2, ship_name: 'Vulture', fitting_name: '',
        source: 'in_fleet', in_fleet: true, count: 3, ship_volunteer_id: null,
    }]
    expect(link_kinds(roles, [DAMNATION]).map(row => row.kind)).toEqual(['shield'])
})

test('ships_for_role dedupes hulls', () => {
    const cyno = entry({ ship_name: 'Devoter', fit_roles: { ...DAMNATION.fit_roles, links: false, cyno: true } })
    expect(ships_for_role([cyno, { ...cyno, key: 'f:2' }], e => e.fit_roles.cyno)).toEqual(['Devoter'])
})
