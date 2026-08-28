import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'
import SkillsetMissingSkills from '@components/blocks/SkillsetMissingSkills.astro'
import type { SkillsetMissingSkillUI } from '@dtypes/layout_components'

const skillset_missing_skills: SkillsetMissingSkillUI = {
    skillsets: {
        name: 'Armor Logistics Cruisers',
        progress: 40,
        missing_skills: [
            { skill_name: 'Remote Armor Repair Systems', skill_level: 4 },
            { skill_name: 'Remote Armor Repair Systems', skill_level: 5 },
            { skill_name: 'Logistics Cruisers', skill_level: 5 },
        ],
    },
    character: {
        character_id: 1,
        character_name: 'Test Pilot',
    },
}

test('Copy clipboard uses skill name plus numeric level so EVE can import the plan', async () => {
    const container = await AstroContainer.create()
    const result = await container.renderToString(SkillsetMissingSkills, {
        props: { skillset_missing_skills },
    })

    expect(result).toContain('Remote Armor Repair Systems 4')
    expect(result).toContain('Remote Armor Repair Systems 5')
    expect(result).toContain('Logistics Cruisers 5')
    expect(result).not.toContain('Remote Armor Repair Systems Remote Armor Repair Systems')
})
