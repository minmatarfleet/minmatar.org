import { describe, expect, it } from 'vitest'
import { composition_changes, hull_filters_for, type DoctrineComposition } from '@helpers/doctrine_editor'

const comp = (parts:Partial<DoctrineComposition>):DoctrineComposition => ({
    primary: [], secondary: [], support: [], utility: [], capitals: [], ...parts,
})

describe('composition_changes', () => {
    it('returns nothing when the composition is unchanged', () => {
        expect(composition_changes(comp({ primary: [1, 2] }), comp({ primary: [2, 1] }))).toEqual([])
    })

    it('lists added, moved and removed fittings in that order', () => {
        const current = comp({ primary: [1, 2], support: [3] })
        const proposed = comp({ primary: [1, 9], utility: [3], capitals: [7] })
        expect(composition_changes(current, proposed)).toEqual([
            { fitting_id: 9, kind: 'added', from: null, to: 'primary' },
            { fitting_id: 7, kind: 'added', from: null, to: 'capitals' },
            { fitting_id: 3, kind: 'moved', from: 'support', to: 'utility' },
            { fitting_id: 2, kind: 'removed', from: 'primary', to: null },
        ])
    })

    it('treats a second role for the same fitting as an addition', () => {
        expect(composition_changes(comp({ primary: [1] }), comp({ primary: [1], capitals: [1] }))).toEqual([
            { fitting_id: 1, kind: 'added', from: null, to: 'capitals' },
        ])
    })
})

describe('hull_filters_for', () => {
    const is_capital = (group:string) => ['Dreadnought', 'Force Auxiliary'].includes(group)

    it('files capitals, logistics and recon hulls', () => {
        expect(hull_filters_for('Dreadnought', is_capital)).toEqual(['capitals'])
        expect(hull_filters_for('Force Auxiliary', is_capital)).toEqual(['capitals', 'logistics'])
        expect(hull_filters_for('Force Recon Ship', is_capital)).toEqual(['recon'])
        expect(hull_filters_for('Battleship', is_capital)).toEqual([])
        expect(hull_filters_for(null, is_capital)).toEqual([])
    })
})
