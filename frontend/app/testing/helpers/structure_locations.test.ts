import { describe, expect, it } from 'vitest'

import type { StructureLocationCard } from '@dtypes/api.minmatar.org'
import {
    has_rig_group,
    in_view,
    parse_rig_groups,
    parse_structure_view,
    percent,
    rig_steps,
    short_isk,
    structure_banner,
    structure_flags,
} from '@helpers/structure_locations'

function card(changes: Partial<StructureLocationCard> = {}): StructureLocationCard {
    return {
        location_id: 1,
        name: 'Amamake - Test',
        short_name: 'Test',
        solar_system_id: 30002537,
        solar_system_name: 'Amamake',
        security: 0.4,
        is_structure: true,
        type_id: 35826,
        type_name: 'Azbel',
        staging: false,
        deployment: false,
        industry_delivery: false,
        fleets: false,
        freight: false,
        freight_route: false,
        market: false,
        prices: false,
        industry_orders: 0,
        audience: 'alliance',
        audience_groups: [],
        good_for: [],
        rigs: [],
        services: [],
        service_modules: [],
        industry: false,
        manufacturing_index: null,
        reaction_index: null,
        facility_tax: null,
        index_discount: 0,
        office_fee_isk: 50_000_000,
        fitting_scanned_at: null,
        reinforce_hour: null,
        route_count: 0,
        planner_facility: null,
        freighter_dock: true,
        you: { clones: 0, items: 0 },
        ...changes,
    }
}

const rig = (group: string) => ({
    name: 'Standup L-Set ...', slot: 'rig', size: 'L', label: group, group,
    tier: 'T1', best_tier: 'T2', is_best: false, use: 'subcap', bonuses: [], upgrade: [],
})

describe('structure views', () => {
    it('keeps old links working', () => {
        expect(parse_structure_view('industry')).toBe('production')
        // Freight and Market are corner icons now, not views.
        expect(parse_structure_view('logistics')).toBe('all')
        expect(parse_structure_view('market')).toBe('all')
        expect(parse_structure_view('clones')).toBe('all')
        expect(parse_structure_view(null)).toBe('all')
        expect(parse_structure_view('reactions')).toBe('reactions')
    })

    it('shows home and deployment stagings under Staging', () => {
        expect(in_view(card({ staging: true }), 'staging')).toBe(true)
        expect(in_view(card({ deployment: true }), 'staging')).toBe(true)
        expect(in_view(card(), 'staging')).toBe(false)
    })

    it('splits industry by rigs and services', () => {
        const azbel = card({ rigs: [rig('subcap_production')] })
        const tatara = card({ rigs: [rig('composite_reactions')], services: ['Reprocessing Facility'] })
        expect(in_view(azbel, 'production')).toBe(true)
        expect(in_view(azbel, 'reactions')).toBe(false)
        expect(in_view(tatara, 'reactions')).toBe(true)
        expect(in_view(tatara, 'reprocessing')).toBe(true)
        expect(in_view(tatara, 'production')).toBe(false)
        expect(in_view(card({ services: ['Manufacturing Plant'] }), 'production')).toBe(true)
    })

    it('keeps unscanned industry structures under Production', () => {
        expect(in_view(card({ good_for: ['industry'] }), 'production')).toBe(true)
        expect(in_view(card({ good_for: ['industry'], services: ['Reactor'] }), 'production')).toBe(false)
    })
})

describe('rigs filter', () => {
    it('reads comma lists and repeated params, dropping unknown groups', () => {
        expect(parse_rig_groups(['subcap_production,capital_production'])).toEqual(['capital_production', 'subcap_production'])
        expect(parse_rig_groups(['grading', 'nonsense'])).toEqual(['grading'])
        expect(parse_rig_groups([])).toEqual([])
    })

    it('matches any picked group', () => {
        const azbel = card({ rigs: [rig('subcap_production'), rig('module_production')] })
        expect(has_rig_group(azbel, [])).toBe(true)
        expect(has_rig_group(azbel, ['capital_production', 'module_production'])).toBe(true)
        expect(has_rig_group(azbel, ['capital_production'])).toBe(false)
    })
})

describe('banners and tags', () => {
    it('gives home and deployment a banner, not a tag, on browse cards', () => {
        const home = card({ staging: true, fleets: true })
        expect(structure_banner(home)).toBe('home')
        expect(structure_banner(card({ deployment: true }))).toBe('deployment')
        expect(structure_banner(card())).toBeNull()
        expect(structure_flags(home, { banner: false }).map((flag) => flag.kind)).toEqual(['fleets'])
        expect(structure_flags(home).map((flag) => flag.kind)).toEqual(['home', 'fleets'])
    })

    it('tags a freight route without freight, and never open orders', () => {
        const stop = card({ freight_route: true, industry_orders: 3 })
        expect(structure_flags(stop).map((flag) => flag.kind)).toEqual(['freight_route'])
    })

    it('tags industry delivery on the hero only, never on the staging', () => {
        const forward = card({ industry_delivery: true })
        expect(structure_flags(forward).map((flag) => flag.kind)).toEqual(['industry_delivery'])
        expect(structure_flags(forward, { banner: false })).toEqual([])
        const home = card({ staging: true, industry_delivery: true })
        expect(structure_flags(home).map((flag) => flag.kind)).toEqual(['home'])
    })
})

describe('card figures', () => {
    it('formats cost indices, tax and office fees', () => {
        expect(percent(0.1309)).toBe('13.09%')
        expect(percent(0.0075)).toBe('0.75%')
        expect(percent(0.01)).toBe('1%')
        expect(percent(null)).toBeNull()
        expect(short_isk(50_000_000)).toBe('50m')
    })

    it('stacks one chevron per tier up to the best tier', () => {
        expect(rig_steps({ tier: 'T1', best_tier: 'T2' })).toEqual([true, false])
        expect(rig_steps({ tier: 'T2', best_tier: 'T2' })).toEqual([true, true])
        expect(rig_steps({ tier: 'Faction', best_tier: 'Faction' })).toEqual([true, true, true])
    })
})
