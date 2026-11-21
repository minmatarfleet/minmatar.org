import { expect, within } from 'storybook/test'
import SkillItem from '@components/blocks/SkillItem.astro'
import type { PlayArgs } from './_helpers'
import { skill_spt_v, skill_gunnery_iv, skill_logi_i } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/SkillItem',
    component: SkillItem,
    parameters: {
        docs: {
            description: {
                component: 'One skill row in the missing-skills dialog and skill plans: a strip of one to five squares (filled for levels already trained) and the skill name with its roman-numeral target level. It appears inside the skillset dialog on `/ships/skillsets/`. The scenarios show a skill needed at level V with nothing trained, a partly trained one and a level I skill.',
            },
        },
    },
    argTypes: {
        skill: { control: 'object', description: 'The skill (`SkillsUI`): name and the level the skillset needs.' },
        current_skill_level: { control: { type: 'number', min: 1, max: 5 }, description: 'The lowest level still missing, which sets how many squares are drawn as learned.' },
    },
    args: { skill: skill_spt_v, current_skill_level: 1 },
}

const squares = (canvasElement: HTMLElement) => ({
    all: canvasElement.querySelectorAll('.skill-square').length,
    learned: canvasElement.querySelectorAll('.skill-square.learned').length,
})

export const NothingTrained = {
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByText('Small Projectile Turret V')).toBeVisible()
        await expect(squares(canvasElement)).toEqual({ all: 5, learned: 0 })
    },
}

export const PartlyTrained = {
    args: { skill: skill_gunnery_iv, current_skill_level: 3 },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByText('Gunnery IV')).toBeVisible()
        await expect(squares(canvasElement)).toEqual({ all: 4, learned: 2 })
    },
}

export const LevelOne = {
    args: { skill: skill_logi_i, current_skill_level: 1 },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByText('Logistics Cruisers I')).toBeVisible()
        await expect(squares(canvasElement).all).toBe(1)
    },
}
