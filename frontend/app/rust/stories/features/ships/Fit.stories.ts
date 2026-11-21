import { expect, within } from 'storybook/test'
import Fit from '@components/blocks/Fit.astro'
import FitSlot from '@components/blocks/FitSlot.astro'
import type { PlayArgs } from './_helpers'
import { rifter_fit_groups } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/Fit',
    component: Fit,
    parameters: {
        docs: {
            description: {
                component: 'A fitting as a plain list of panels, one per slot group (High, Medium, Low, Rig, Cargo), each module a badge with its icon and name, with the amount for stacked items ("2 x Gyrostabilizer II"). It is the text-style fit view used on fitting pages and fleet fit summaries. Groups with no modules are skipped. The scenarios show a full Rifter fit, a single group and no groups.',
            },
        },
    },
    argTypes: {
        fitting_groups: { control: 'object', description: 'The groups (`FittingGroup[]`): a name and its modules (`CargoItem`: id, name, optional amount).' },
    },
    args: { fitting_groups: rifter_fit_groups },
}

export const RifterFit = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('heading', { level: 2 }).map(h => h.textContent)).toEqual(['High Slots', 'Medium Slots', 'Low Slots', 'Cargo'])
        await expect(canvas.getAllByRole('listitem')).toHaveLength(3 + 2 + 2 + 1)
        await expect(canvas.getByText('2 x Gyrostabilizer II')).toBeVisible()
        await expect(canvas.getByText('Republic Fleet 200mm Autocannon')).toBeVisible()
    },
}

export const SingleGroup = {
    args: { fitting_groups: [rifter_fit_groups[1]] },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('heading', { level: 2 })).toHaveLength(1)
        await expect(canvas.getByText('5MN Microwarpdrive II')).toBeVisible()
    },
}

export const EmptyGroupsSkipped = {
    args: { fitting_groups: [{ name: 'Rig Slots', modules: [] }, { name: 'Drones', modules: [] }] },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).queryByRole('heading')).toBeNull()
    },
}
