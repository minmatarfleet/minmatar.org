import { describe, it, expect } from 'vitest'
import { fleet_commander_label } from '@helpers/fleet_commander'

describe('fleet_commander_label', () => {
    it('names the main alone on the main', () => {
        expect(fleet_commander_label({ fleet_commander_name: 'BearThatCares', fleet_commander_alt_name: null }, 'as'))
            .toBe('BearThatCares')
    })

    it('names the main as the alt when the fleet runs on an alt', () => {
        expect(fleet_commander_label({ fleet_commander_name: 'BearThatCares', fleet_commander_alt_name: 'Henri Gray' }, 'as'))
            .toBe('BearThatCares as Henri Gray')
    })
})
