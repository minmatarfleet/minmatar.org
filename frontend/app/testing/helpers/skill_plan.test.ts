import { describe, expect, it } from 'vitest'
import { format_skill_plan, format_skill_plan_line } from '@helpers/skill_plan'

describe('format_skill_plan', () => {
    it('uses EVE Roman numerals, one line per missing level', () => {
        expect(format_skill_plan_line('EDENCOM Frigate', 1)).toBe('EDENCOM Frigate I')
        expect(format_skill_plan_line('Weapon Upgrades', 3)).toBe('Weapon Upgrades III')
        expect(format_skill_plan_line('Medium Vorton Projector', 5)).toBe('Medium Vorton Projector V')

        expect(
            format_skill_plan([
                { skill_name: 'EDENCOM Frigate', skill_level: 1 },
                { skill_name: 'EDENCOM Frigate', skill_level: 2 },
                { skill_name: 'EDENCOM Frigate', skill_level: 3 },
                { skill_name: 'Weapon Upgrades', skill_level: 3 },
                { skill_name: 'Weapon Upgrades', skill_level: 4 },
            ]),
        ).toBe(
            [
                'EDENCOM Frigate I',
                'EDENCOM Frigate II',
                'EDENCOM Frigate III',
                'Weapon Upgrades III',
                'Weapon Upgrades IV',
            ].join('\n'),
        )
    })
})
