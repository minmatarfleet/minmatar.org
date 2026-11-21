import { expect, within } from 'storybook/test'
import FitSlot from '@components/blocks/FitSlot.astro'
import type { PlayArgs } from './_helpers'
import { fit_slot_single, fit_slot_stacked, fit_slot_officer_long } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/FitSlot',
    component: FitSlot,
    parameters: {
        docs: {
            description: {
                component: 'One module in a fit list: a badge with the module icon and its name, prefixed with the amount when more than one is fitted. It is the row inside the Fit block on fitting pages. The scenarios show a single module, a stack of identical modules and an officer module with a long name.',
            },
        },
    },
    argTypes: {
        fittable: { control: 'object', description: 'The module or cargo item (`CargoItem`): type id, name and an optional amount.' },
    },
    args: { fittable: fit_slot_single },
}

export const SingleModule = {
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByText('200mm AutoCannon II')).toBeVisible()
        await expect(canvasElement.querySelector('img')?.getAttribute('src')).toContain('2889')
    },
}

export const Stacked = {
    args: { fittable: fit_slot_stacked },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByText('3 x Gyrostabilizer II')).toBeVisible()
    },
}

export const OfficerLongName = {
    args: { fittable: fit_slot_officer_long },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByText(/Ramaku's Modified 200mm AutoCannon/)).toBeVisible()
    },
}
