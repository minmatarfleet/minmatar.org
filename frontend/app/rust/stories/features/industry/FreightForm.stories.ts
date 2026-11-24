import { expect, within } from 'storybook/test'
import FreightForm from '@components/blocks/FreightForm.astro'
import {
    freight_calculator_route_key,
    freight_calculator_routes,
    no_freight_calculator_routes,
} from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Industry/FreightForm',
    component: FreightForm,
    parameters: {
        docs: {
            description: {
                component: 'Quotes routes the pilot can use. When the route list is empty, the calculator shows an empty state.',
            },
        },
    },
    args: {
        freight_routes_data: freight_calculator_routes,
        default_route: freight_calculator_route_key,
    },
}

export const AvailableRoute = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('option', { name: 'Jita → Amamake' })).toHaveValue(freight_calculator_route_key)
        await expect(canvas.getByRole('button', { name: 'Calculate' })).toBeEnabled()
    },
}

export const NoAvailableRoutes = {
    args: { freight_routes_data: no_freight_calculator_routes, default_route: '' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No freight routes are available.')).toBeVisible()
        await expect(canvas.queryByRole('button', { name: 'Calculate' })).toBeNull()
    },
}
