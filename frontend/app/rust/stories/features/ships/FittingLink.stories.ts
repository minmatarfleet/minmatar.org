import { expect, within } from 'storybook/test'
import FittingLink from '@components/blocks/FittingLink.astro'
import type { PlayArgs } from './_helpers'
import { rifter_fitting } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/FittingLink',
    component: FittingLink,
    parameters: {
        docs: {
            description: {
                component: 'The link (or button) to a fitting page, `/ships/fittings/normal/<id>-<name>/`. It wraps a FittingCard in the doctrine and fitting grids and is a small red button on fleet pages. Without a name the URL is the bare id and the page redirects to the canonical slug; when the 3D viewer is enabled the link switches to the render view on wide screens.',
            },
        },
    },
    argTypes: {
        fitting_id: { control: 'number', description: 'Fitting id, used in the URL.' },
        fitting_name: { control: 'text', description: 'Names the URL slug; null or empty leaves just the id.' },
        is_button: { control: 'boolean', description: 'Render a Button instead of a bare anchor.' },
        size: { control: 'inline-radio', options: ['lg', 'sm'], description: 'Button size (only with `is_button`).' },
        color: { control: 'select', options: ['fleet-red', 'alliance-blue', 'militia-purple', 'green', 'transparent'], description: 'Button color (only with `is_button`).' },
        narrow: { control: 'boolean', description: 'Narrow button padding (only with `is_button`).' },
    },
    args: { fitting_id: rifter_fitting.id, fitting_name: rifter_fitting.fitting_name, is_button: false, slots: { default: rifter_fitting.fitting_name } },
}

export const Anchor = {
    play: async ({ canvasElement }: PlayArgs) => {
        const link = within(canvasElement).getByRole('link', { name: 'Rifter - Amamake Brawler' })
        await expect(link.getAttribute('href')).toBe('/ships/fittings/normal/1201-rifter-amamake-brawler/')
    },
}

export const WithoutName = {
    args: { fitting_name: null, slots: { default: 'Open fitting 1201' } },
    play: async ({ canvasElement }: PlayArgs) => {
        const link = within(canvasElement).getByRole('link', { name: 'Open fitting 1201' })
        await expect(link.getAttribute('href')).toBe('/ships/fittings/normal/1201/')
    },
}

export const AsButton = {
    args: { is_button: true, slots: { default: 'View fitting' } },
    play: async ({ canvasElement }: PlayArgs) => {
        const link = within(canvasElement).getByRole('link', { name: 'View fitting' })
        await expect(link.getAttribute('href')).toBe('/ships/fittings/normal/1201-rifter-amamake-brawler/')
        await expect(link).toHaveClass('button')
    },
}
