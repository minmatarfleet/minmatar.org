import { expect, within } from 'storybook/test'
import SkillsetMissingSkills from '@components/blocks/SkillsetMissingSkills.astro'
import type { PlayArgs } from './_helpers'
import {
    missing_skills_partial, missing_skills_with_repeats, missing_skills_none, account_characters,
} from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/SkillsetMissingSkills',
    component: SkillsetMissingSkills,
    parameters: {
        docs: {
            description: {
                component: 'The dialog that opens from a skillset tile (`/ships/skillsets/`): the skills a character still has to train for a skillset, each as five squares for its level, plus a button that copies the plan to the clipboard. Pilots with several characters get a portrait picker that swaps the dialog by htmx. The scenarios show a partly trained skillset, repeated skills at rising levels, a fully trained skillset and the character picker.',
            },
        },
    },
    argTypes: {
        skillset_missing_skills: { control: 'object', description: 'The skillset with its missing skills and the character they were computed for.' },
        characters: { control: 'object', description: 'All of the pilot\'s characters. The picker only appears with two or more and a `partial_url`.' },
        skillset_name: { control: 'text', description: 'Skillset name sent to the swap request; defaults to the skillset\'s own name.' },
        partial_url: { control: 'text', description: 'The partial the picker swaps from. Empty hides the picker.' },
    },
    args: { skillset_missing_skills: missing_skills_partial, characters: [], partial_url: '' },
}

export const PartlyTrained = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 2 })).toHaveTextContent('Magic 14 Skillset: Missing skills')
        await expect(canvas.getByText('3 skills missing')).toBeVisible()
        await expect(canvas.getByText('Gunnery IV')).toBeVisible()
        await expect(canvas.getByText('Small Projectile Turret V')).toBeVisible()
        await expect(canvasElement.querySelector('#copy-skills')).not.toBeNull()
    },
}

export const RepeatedSkills = {
    args: { skillset_missing_skills: missing_skills_with_repeats },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('5 skills missing')).toBeVisible()
        await expect(canvas.getByText('Logistics Cruisers I')).toBeVisible()
        await expect(canvas.getByText('Logistics Cruisers III')).toBeVisible()
    },
}

export const FullyTrained = {
    args: { skillset_missing_skills: missing_skills_none },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('0 skills missing')).toBeVisible()
        await expect(canvas.getByText('Skillset is fully trained')).toBeVisible()
        // Nothing to copy.
        await expect(canvasElement.querySelector('#copy-skills')).toBeNull()
    },
}

export const CharacterPicker = {
    args: { characters: account_characters, partial_url: '/partials/missing_skills_modal_component/' },
    parameters: { htmx: { '/partials/missing_skills_modal_component/': '<div id="skillset-missing-skills">Swapped</div>' } },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        const group = canvas.getByRole('group')
        await expect(within(group).getAllByRole('button')).toHaveLength(3)
        await expect(canvas.getByRole('button', { name: "Kel'dar Atram (Main)" })).toBeDisabled()
        const alt = canvas.getByRole('button', { name: 'Rattini Pilot' })
        await expect(alt.getAttribute('hx-get')).toBe('/partials/missing_skills_modal_component/?character_id=2112954533&skillset_name=Magic%2014')
    },
}
