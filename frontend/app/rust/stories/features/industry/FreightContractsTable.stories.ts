import { expect, within } from 'storybook/test'
import FreightContractsTable from '@components/blocks/FreightContractsTable.astro'
import { freight_history, freight_mixed } from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Industry/FreightContractsTable',
    component: FreightContractsTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'The ledger of courier contracts on the alliance freight service, at `/market/freight/contracts/` and its history page. Each row shows who issued the contract, the route, its status, volume, collateral, reward and which hauler is servicing it ("Not taken" until someone accepts).',
                    'Outside history a button leads to the historical contracts. Scenarios show an empty ledger, a mix of outstanding, in-progress and finished contracts, and a long history list.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        contracts: { control: 'object', description: '`FreightContract[]`, newest first.' },
        is_history: { control: 'boolean', description: 'Hides the "View all historical contracts" button.' },
    },
    args: { contracts: freight_mixed, is_history: false },
}

export const MixedStatuses = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('columnheader')).toHaveLength(8)
        await expect(canvas.getAllByRole('row')).toHaveLength(4)
        await expect(canvas.getByText('Outstanding')).toBeVisible()
        await expect(canvas.getByText('In progress')).toBeVisible()
        await expect(canvas.getByText('Recently completed')).toBeVisible()
        await expect(canvas.getByText('Jita IV - Moon 4 - Caldari Navy Assembly Plant → Amamake - Rattini Tribe Freeport')).toBeVisible()
        await expect(canvas.getByText('2,500,000,000')).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'View all historical contracts' })).toHaveAttribute('href', '/market/freight/contracts/history/')
    },
}

export const NotTakenUntilAccepted = {
    args: { contracts: freight_mixed.slice(0, 2) },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByText('Not taken')).toHaveLength(1)
        await expect(canvas.getByText('Auga Hauler')).toBeVisible()
    },
}

export const Empty = {
    args: { contracts: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.queryAllByRole('row')).toHaveLength(1)
        await expect(canvas.getByRole('link', { name: 'View all historical contracts' })).toBeVisible()
    },
}

export const History = {
    args: { contracts: freight_history, is_history: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(13)
        await expect(canvas.queryByRole('link', { name: 'View all historical contracts' })).toBeNull()
        await expect(canvas.getAllByText('Recently completed')).toHaveLength(12)
    },
}
