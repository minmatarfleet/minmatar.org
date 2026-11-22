import { expect, within } from 'storybook/test'
import MoonProfitTable from '@components/blocks/universe/MoonProfitTable.astro'
import { moon_profit_r16, moon_net_r16, moon_profit_r4_loss, moon_net_r4_loss } from '../../../fixtures/features/intel-and-combat'

export default {
    title: 'Features/Intel and combat/MoonProfitTable',
    component: MoonProfitTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'The Profit tab of a moon row on Universe › Moons (`/universe/#moons`): a month of Metenox drill output, a month of fuel (200 Magmatic Gas and 5 of the cheapest fuel block an hour), then net. Prices are Jita guide prices from the last price run, and the footer says when that was.',
                    'The scenarios show a moon that pays, a moon whose fuel costs more than it makes (net in the warning colour), and a moon not priced yet.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        profit: { control: 'object', description: 'Output and fuel lines a month (`MoonProfit`); null until the moon is priced.' },
        net: { control: 'number', description: 'Output value minus fuel a month.' },
    },
    args: { profit: moon_profit_r16, net: moon_net_r16 },
}

type Ctx = { canvasElement: HTMLElement }

export const Profitable = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('table', { name: 'Profit' })).toBeInTheDocument()
        await expect(canvas.getByText('Platinum')).toBeInTheDocument()
        await expect(canvas.getByText('Magmatic Gas')).toBeInTheDocument()
        await expect(canvas.getByRole('rowheader', { name: 'Net a month' })).toBeInTheDocument()
        await expect(canvasElement.querySelectorAll('tbody')).toHaveLength(2)
    },
}

export const LosesIsk = {
    name: 'Fuel costs more than it makes',
    args: { profit: moon_profit_r4_loss, net: moon_net_r4_loss },
    play: async ({ canvasElement }: Ctx) => {
        const net = canvasElement.querySelector('tfoot td:last-child') as HTMLElement
        await expect(net.textContent).toMatch(/^-/)
        await expect(net.classList.contains('moon-profit__loss')).toBe(true)
    },
}

export const NotPriced = {
    name: 'Not priced yet',
    args: { profit: null, net: null },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Not priced yet')).toBeInTheDocument()
        await expect(canvasElement.querySelector('table')).toBeNull()
    },
}
