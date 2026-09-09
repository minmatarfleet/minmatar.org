import { describe, expect, it } from 'vitest'

import {
    infer_fit_match,
    primary_fitting,
    primary_fitting_for_ship,
} from '@/data/capital-guide/fittings'
import type { Fitting } from '@dtypes/api.minmatar.org'

function fitting(partial: Pick<Fitting, 'id' | 'name' | 'ship_id'> & Partial<Fitting>): Fitting {
    return {
        description: '',
        created_at: new Date(0),
        updated_at: new Date(0),
        eft_format: '',
        minimum_pod: '',
        recommended_pod: '',
        latest_version: '',
        known_key: null,
        refits: [],
        tags: ['faction_warfare'],
        ...partial,
    }
}

const apostle_id = 37604

const library: Fitting[] = [
    fitting({ id: 15, name: '[FL33T] Active Apostle', ship_id: apostle_id }),
    fitting({ id: 17, name: '[FL33T] Buffer Apostle', ship_id: apostle_id }),
    fitting({ id: 228, name: '[FL33T] Active Ninazu', ship_id: 37607 }),
    fitting({ id: 440, name: '[FL33T] Active Geno Ninazu', ship_id: 37607 }),
    fitting({ id: 16, name: '[FL33T] Active Minokawa', ship_id: 37605 }),
    fitting({ id: 335, name: '[FL33T] Buffer Minokawa', ship_id: 37605 }),
    fitting({ id: 441, name: '[FL33T] Active Geno Minokawa', ship_id: 37605 }),
]

describe('capital guide primary fitting', () => {
    it('infers Buffer from buffer or passive notes', () => {
        expect(infer_fit_match('Recommended. Buffer armor fax, often in pairs.')).toBe('Buffer')
        expect(infer_fit_match('Start with the Passive Apostle fit')).toBe('Buffer')
        expect(infer_fit_match('Active armor fax')).toBe('Active')
    })

    it('links Apostle hulls to Buffer Apostle instead of the older Active fit', () => {
        const primary = primary_fitting_for_ship(apostle_id, library, {
            notes: 'Recommended. Buffer (passive) armor fax, often in pairs.',
            fit_match: 'Buffer',
        })
        expect(primary?.id).toBe(17)
        expect(primary?.name).toContain('Buffer Apostle')
    })

    it('prefers Buffer Minokawa when the hull is described as buffer', () => {
        const primary = primary_fitting_for_ship(37605, library, {
            notes: 'Buffer shield fax, often in pairs.',
        })
        expect(primary?.id).toBe(335)
    })

    it('prefers the non-Geno Active Ninazu over Active Geno Ninazu', () => {
        const primary = primary_fitting_for_ship(37607, library, {
            fit_match: 'Active Ninazu',
            notes: 'Active armor fax',
        })
        expect(primary?.id).toBe(228)
    })

    it('falls back to the first fit when no name matches', () => {
        const only_active = [
            fitting({ id: 15, name: '[FL33T] Active Apostle', ship_id: apostle_id }),
        ]
        expect(primary_fitting(only_active, { fit_match: 'Buffer' })?.id).toBe(15)
        expect(primary_fitting([], { fit_match: 'Buffer' })).toBeNull()
    })
})
