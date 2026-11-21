import { expect, userEvent, waitFor, within } from 'storybook/test'
import CargoHold from '@components/blocks/CargoHold.astro'
import { cargo_fleet_fit, cargo_no_amounts, cargo_single } from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Industry/CargoHold',
    component: CargoHold,
    parameters: {
        docs: {
            description: {
                component: [
                    'A collapsible list of the items in a ship fit\'s cargo hold, shown under a fitting on the fitting and doctrine pages (`/market/fitting_orders/`, doctrine detail). The slot is the toggle label; clicking it expands a row of item icons labelled "<amount> x <name>".',
                    'Scenarios show a fit with several stacks, a single stack, and items with no amount, where the label is just the name.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        cargo: { control: 'object', description: '`CargoItem[]`: type id, name and an optional stack size.' },
    },
    args: { cargo: cargo_fleet_fit, slots: { default: 'Cargo hold' } },
}

export const FleetFitCargo = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const toggle = canvas.getByRole('button', { name: /Cargo hold/ })
        await expect(toggle).toBeVisible()
        // Collapsed: the stacks are in the page but hidden until the toggle is clicked.
        await expect(canvas.getByText('6 x 200mm AutoCannon II')).not.toBeVisible()
        await expect(canvas.getAllByText(/ x /)).toHaveLength(cargo_fleet_fit.length)
    },
}

// Alpine's x-collapse measures layout, so the expand step needs a real browser.
export const ExpandsOnClick = {
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.click(canvas.getByRole('button', { name: /Cargo hold/ }))
        await waitFor(() => expect(canvas.getByText('6 x 200mm AutoCannon II')).toBeVisible())
        await expect(canvas.getByText('150 x Nanite Repair Paste')).toBeVisible()
    },
}

export const SingleStack = {
    args: { cargo: cargo_single },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('300 x Nanite Repair Paste')).toBeInTheDocument()
    },
}

export const WithoutAmounts = {
    args: { cargo: cargo_no_amounts },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Rifter')).toBeInTheDocument()
        await expect(canvas.getByText('Nanite Repair Paste')).toBeInTheDocument()
        await expect(canvas.queryByText(/ x /)).toBeNull()
    },
}
