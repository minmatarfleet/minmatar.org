import { describe, expect, it } from 'vitest'

import type { StructureLocationCard } from '@dtypes/api.minmatar.org'
import {
    has_rig_group,
    in_view,
    parse_rig_groups,
    parse_structure_view,
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
        fleets: false,
        freight: false,
        market: false,
        prices: false,
        industry_orders: 0,
        audience: 'alliance',
        audience_groups: [],
        good_for: [],
        rigs: [],
        services: [],
        fitting_scanned_at: null,
        reinforce_hour: null,
        route_count: 0,
        planner_facility: null,
        freighter_dock: true,
        you: { clones: 0, items: 0 },
        ...changes,
    }
}

const rig = (group: string) => ({ name: 'Standup L-Set ...', slot: 'rig', size: 'L', label: group, group })

describe('structure views', () => {
    it('keeps old links working', () => {
        expect(parse_structure_view('industry')).toBe('production')
        expect(parse_structure_view('logistics')).toBe('freight')
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
})
