import { describe, expect, it } from 'vitest'

import { dynamic_key, i18n, t_key } from '@helpers/i18n'
import { BURST_KINDS } from '@helpers/fleet_roles'
import type { FleetFittingRole } from '@helpers/api.minmatar.org/fleets'
import { esi_token_roles } from '@dtypes/api.minmatar.org'
import { fleet_roles, fleet_roles_subtypes } from '@dtypes/layout_components'
import { ui } from '@i18n/ui'

const { t } = i18n(new URL('https://my.minmatar.org/'))
const has_key = (key: string) => Object.prototype.hasOwnProperty.call(ui.en, key)

describe('t_key / dynamic_key', () => {
    it('build the same string as the template literal they replace', () => {
        for (const value of ['shield', 7, undefined, null, '']) {
            expect(t_key('burst_kind_', value)).toBe(`burst_kind_${value}`)
            expect(t_key('', value, '.page_title')).toBe(`${value}.page_title`)
        }
        expect(dynamic_key('published')).toBe('published')
        expect(dynamic_key(undefined)).toBeUndefined()
    })

    it('leave t() output unchanged, including undefined for a missing key', () => {
        expect(t(t_key('burst_kind_', 'shield'))).toBe(ui.en.burst_kind_shield)
        expect(t(t_key('burst_kind_', 'not_a_kind'))).toBeUndefined()
        expect(t(dynamic_key('not_a_key'))).toBeUndefined()
    })
})

// Each dynamic key family must cover every value its code can produce; otherwise the label renders blank.
describe('dynamic i18n key families cover their values', () => {
    const missing = (keys: string[]) => keys.filter((key) => !has_key(key))

    it('burst_kind_<kind> (FleetShipRow, fleet_pick_ships_modal)', () => {
        expect(missing(BURST_KINDS.map((kind) => `burst_kind_${kind}`))).toEqual([])
    })

    it('fitting_role_<role> (fleet_add_ships_modal)', () => {
        const roles: FleetFittingRole[] = ['primary', 'secondary', 'support', 'utility']
        expect(missing(roles.map((role) => `fitting_role_${role}`))).toEqual([])
    })

    it('<role>_label and <subtype>_links (fleet_role_item)', () => {
        expect(missing(fleet_roles_subtypes.map((subtype) => `${subtype}_links`))).toEqual([])
        // Links are listed per subtype; a request without one falls back to the raw role name ('links').
        expect(missing(fleet_roles.map((role) => `${role}_label`))).toEqual(['links_label'])
    })

    it('ESI token roles (FixESITokenButton)', () => {
        expect(missing([...esi_token_roles])).toEqual([])
    })
})
