import { expect, within } from 'storybook/test'
import OrderItem from '@components/blocks/OrderItem.astro'
import {
    order_claiming,
    order_fulfilled,
    order_in_progress,
    order_long,
    order_overdue,
    order_unclaimed,
} from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Industry/OrderItem',
    component: OrderItem,
    parameters: {
        docs: {
            description: {
                component: [
                    'One row of an industry order: who asked for it, the hulls and modules wanted (with quantities), the builders on it, and the date it is needed by with how much time is left. The whole row links to the order page (`/industry/orders/<id>/`). It is the unit of the order lists at `/industry/orders/` and `/industry/orders/history/`.',
                    'Scenarios show an order nobody has claimed, one in progress with several hulls and two builders, one past its deadline, a delivered one, a provisional order still in its claiming window, and an order with a very long item list and pilot name.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        order: { control: 'object', description: 'The order row (`IndustryOrderUI`): items, builders in `assigned_to`, deadline, fulfilment and provisional state.' },
        order_breakdown: { control: 'object', description: 'Per-item breakdown rendered under the row (the order detail view). Omitted in lists.' },
        primary_character_id: { control: 'number', description: 'The viewer\'s primary character, for the breakdown\'s claim buttons.' },
        claim_disabled_reason: { control: 'text', description: 'Why claiming is unavailable, shown in the breakdown.' },
        location_name: { control: 'text', description: 'The station the order is built for.' },
        alert: { control: 'object', description: 'Opens the alert dialog on load (used after creating or editing an order).' },
    },
    args: { order: order_unclaimed, location_name: 'Amamake - Rattini Tribe Freeport' },
}

export const Unclaimed = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const link = canvasElement.querySelector('a.order-item-link')
        await expect(link).toHaveAttribute('href', '/industry/orders/8412/')
        await expect(canvasElement.querySelector('#order-item-8412')).not.toBeNull()
        await expect(canvas.getByText('Contractor')).toBeVisible()
        await expect(canvas.getByText("Kel'dar Atram")).toBeVisible()
        await expect(canvas.getByText('Hurricane')).toBeInTheDocument()
        await expect(canvasElement.querySelector('[data-tippy-content="Needed by"]')).not.toBeNull()
        await expect(canvas.getByText(/left \(\d+%\)/)).toBeVisible()
    },
}

export const InProgress = {
    args: { order: order_in_progress },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Hurricane')).toBeInTheDocument()
        await expect(canvas.getByText('Muninn')).toBeInTheDocument()
        await expect(canvas.getByText('Scimitar')).toBeInTheDocument()
        await expect(canvas.getByText('Amamake Defender')).toBeInTheDocument()
        await expect(canvas.getByText('Auga Hauler')).toBeInTheDocument()
        await expect(canvas.getByText('Rattini Pilot')).toBeVisible()
    },
}

export const Overdue = {
    args: { order: order_overdue, location_name: 'Rens VI - Moon 8 - Brutor Tribe Treasury' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const status = canvas.getByText(/overdue/)
        await expect(status).toBeVisible()
        // Overdue open orders are flagged red.
        await expect(status).toHaveClass('text-red')
    },
}

export const Fulfilled = {
    args: { order: order_fulfilled },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/^Completed on /)).toBeVisible()
        await expect(canvas.queryByText(/overdue/)).toBeNull()
        await expect(canvas.getByText('Vagabond')).toBeInTheDocument()
    },
}

export const ClaimingWindow = {
    args: { order: order_claiming },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/^Claiming · \d+ hours$/)).toBeVisible()
        await expect(canvas.queryByText(/left \(/)).toBeNull()
    },
}

export const LongNamesAndManyItems = {
    args: { order: order_long },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/Logistics Wing/)).toBeVisible()
        for (const name of ['Rifter', 'Stabber Fleet Issue', 'Hurricane Fleet Issue', 'Cynabal', 'Republic Fleet Firetail', 'Svipul', 'Vargur'])
            await expect(canvas.getByText(name)).toBeInTheDocument()
    },
}
