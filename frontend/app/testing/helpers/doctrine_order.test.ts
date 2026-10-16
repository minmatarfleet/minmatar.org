import { describe, expect, it } from 'vitest'
import { sort_doctrines } from '@helpers/doctrine_order'
import type { DoctrineType, DoctrineTypes, FittingItem } from '@dtypes/layout_components'

function fitting(overrides: Partial<FittingItem>): FittingItem {
    return {
        fitting_name: 'fit',
        fitting_type: 'FL33T',
        ship_type: 'Frigate',
        ship_name: 'Rifter',
        ship_id: 1,
        id: 1,
        eft_format: '',
        ship_meta: 'Tech I',
        ...overrides,
    }
}

function doctrine(
    name: string,
    type: DoctrineTypes,
    ship: Partial<FittingItem>,
    id = name.length,
): DoctrineType {
    return {
        id,
        name,
        type,
        created_at: new Date(0),
        updated_at: new Date(0),
        description: '',
        primary_fittings: [fitting(ship)],
        secondary_fittings: [],
        support_fittings: [],
        utility_fittings: [],
        location_ids: [],
    }
}

describe('sort_doctrines', () => {
    it('reads small hulls before large hulls, then T1, faction, and T2', () => {
        const sorted = sort_doctrines([
            doctrine('TFIs', 'strategic', {
                ship_type: 'Battleship',
                ship_name: 'Tempest Fleet Issue',
                ship_meta: 'Faction',
                ship_id: 17732,
            }),
            doctrine('Assfrigs', 'non_strategic', {
                ship_type: 'Assault Frigate',
                ship_name: 'Enyo',
                ship_meta: 'Tech II',
                ship_id: 12044,
            }),
            doctrine('Napocs', 'strategic', {
                ship_type: 'Battleship',
                ship_name: 'Apocalypse Navy Issue',
                ship_meta: 'Faction',
                ship_id: 17726,
            }),
            doctrine('Torpfields', 'non_strategic', {
                ship_type: 'Battleship',
                ship_name: 'Typhoon',
                ship_meta: 'Tech I',
                ship_id: 644,
            }),
            doctrine('HML Osprey Navy Issue', 'non_strategic', {
                ship_type: 'Cruiser',
                ship_name: 'Osprey Navy Issue',
                ship_meta: 'Faction',
                ship_id: 29340,
            }),
            doctrine('Cruisefields', 'non_strategic', {
                ship_type: 'Battleship',
                ship_name: 'Raven',
                ship_meta: 'Tech I',
                ship_id: 638,
            }),
        ])

        expect(sorted.map((item) => item.name)).toEqual([
            'Assfrigs',
            'HML Osprey Navy Issue',
            'Cruisefields',
            'Torpfields',
            'Napocs',
            'TFIs',
        ])
    })

    it('keeps a strategic doctrine next to the non-strategic doctrine of the same ship', () => {
        const sorted = sort_doctrines([
            doctrine('Wolf strat', 'strategic', {
                ship_type: 'Assault Frigate',
                ship_name: 'Wolf',
                ship_meta: 'Tech II',
                ship_id: 11371,
            }),
            doctrine('Enyo', 'non_strategic', {
                ship_type: 'Assault Frigate',
                ship_name: 'Enyo',
                ship_meta: 'Tech II',
                ship_id: 12044,
            }),
            doctrine('Wolf', 'non_strategic', {
                ship_type: 'Assault Frigate',
                ship_name: 'Wolf',
                ship_meta: 'Tech II',
                ship_id: 11371,
            }),
            doctrine('Wolf experimental', 'experimental', {
                ship_type: 'Assault Frigate',
                ship_name: 'Wolf',
                ship_meta: 'Tech II',
                ship_id: 11371,
            }),
        ])

        expect(sorted.map((item) => item.name)).toEqual([
            'Enyo',
            'Wolf',
            'Wolf strat',
            'Wolf experimental',
        ])
    })

    it('puts a T2 frigate before a T1 destroyer, and T3 after T2 of the same size', () => {
        const sorted = sort_doctrines([
            doctrine('Thrasher', 'non_strategic', {
                ship_type: 'Destroyer',
                ship_name: 'Thrasher',
                ship_meta: 'Tech I',
                ship_id: 16242,
            }),
            doctrine('Loki', 'non_strategic', {
                ship_type: 'Strategic Cruiser',
                ship_name: 'Loki',
                ship_meta: 'Tech III',
                ship_id: 29990,
            }),
            doctrine('Enyo', 'non_strategic', {
                ship_type: 'Assault Frigate',
                ship_name: 'Enyo',
                ship_meta: 'Tech II',
                ship_id: 12044,
            }),
            doctrine('Caracal', 'non_strategic', {
                ship_type: 'Cruiser',
                ship_name: 'Caracal',
                ship_meta: 'Tech I',
                ship_id: 621,
            }),
            doctrine('Eagle', 'strategic', {
                ship_type: 'Heavy Assault Cruiser',
                ship_name: 'Eagle',
                ship_meta: 'Tech II',
                ship_id: 12011,
            }),
        ])

        expect(sorted.map((item) => item.name)).toEqual([
            'Enyo',
            'Thrasher',
            'Caracal',
            'Eagle',
            'Loki',
        ])
    })

    it('does not mutate the input list', () => {
        const input = [
            doctrine('Tempest', 'non_strategic', {
                ship_type: 'Battleship',
                ship_name: 'Tempest',
                ship_id: 639,
            }),
            doctrine('Rifter', 'non_strategic', {
                ship_type: 'Frigate',
                ship_name: 'Rifter',
                ship_id: 587,
            }),
        ]
        const snapshot = input.map((item) => item.name)

        sort_doctrines(input)

        expect(input.map((item) => item.name)).toEqual(snapshot)
    })
})
