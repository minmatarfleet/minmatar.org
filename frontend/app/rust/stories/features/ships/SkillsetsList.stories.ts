import { expect, within, userEvent, waitFor } from 'storybook/test'
import SkillsetsList from '@components/blocks/SkillsetsList.astro'
import type { PlayArgs } from './_helpers'
import { skillsets_busy, skillsets_only_new_player, skillset_pilot } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/SkillsetsList',
    component: SkillsetsList,
    parameters: {
        docs: {
            description: {
                component: 'The skillset catalog on `/ships/skillsets/` (also a tab on the learning center): category chips (All, New Players, Subcapitals, Capitals) filter a grid of skillset tiles showing progress for the selected character. Each tile opens the missing-skills dialog. The scenarios show a full catalog, a short one where only one chip applies, a finished skillset and an empty list.',
            },
        },
    },
    argTypes: {
        skillsets: { control: 'object', description: 'The skillsets (`Skillset[]`): name, progress 0-100 and the missing skills. A name known to `skillset_categories.ts` gets a category chip.' },
        character: { control: 'object', description: 'The character whose progress is shown (`CharacterBasic`); used in the dialog URL.' },
    },
    args: { skillsets: skillsets_busy, character: skillset_pilot },
}

const tiles = (canvasElement: HTMLElement) => Array.from(canvasElement.querySelectorAll('.skillsets-catalog__item')) as HTMLElement[]

export const FullCatalog = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(tiles(canvasElement)).toHaveLength(6)
        for (const label of ['All categories', 'New Players', 'Subcapitals', 'Capitals'])
            await expect(canvas.getByRole('button', { name: new RegExp(label) })).toBeVisible()
        await expect(canvas.getByText('Magic 14')).toBeVisible()
    },
}

export const FilterByCategory = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await userEvent.click(canvas.getByRole('button', { name: /Capitals/ }))
        // Alpine applies the filter after the click, so wait for the visible tiles to settle.
        const visible = () => tiles(canvasElement).filter(tile => tile.style.display !== 'none')
        await waitFor(() => expect(visible()).toHaveLength(1))
        await expect(visible()[0]).toHaveTextContent('Revelation/RNI')
        await userEvent.click(canvas.getByRole('button', { name: /All categories/ }))
        await waitFor(() => expect(visible()).toHaveLength(6))
    },
}

export const FilterChipsReportTheirState = {
    // aria-pressed is bound by Alpine; vitest's DOM does not apply the initial bindings, a browser does.
    tags: ['browser'],
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        const all = canvas.getByRole('button', { name: /All categories/ })
        const capitals = canvas.getByRole('button', { name: /Capitals/ })
        await waitFor(() => expect(all).toHaveAttribute('aria-pressed', 'true'))
        await userEvent.click(capitals)
        await waitFor(() => expect(capitals).toHaveAttribute('aria-pressed', 'true'))
        await expect(all).toHaveAttribute('aria-pressed', 'false')
    },
}

export const OnlyNewPlayerSkillsets = {
    args: { skillsets: skillsets_only_new_player },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(tiles(canvasElement)).toHaveLength(2)
        await expect(canvas.getByRole('button', { name: /New Players/ })).toBeVisible()
        // Chips with no skillsets are not offered.
        await expect(canvas.queryByRole('button', { name: /Capitals/ })).toBeNull()
    },
}

export const NoSkillsets = {
    args: { skillsets: [] },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByText('No skillsets found')).toBeVisible()
        await expect(tiles(canvasElement)).toHaveLength(0)
    },
}
