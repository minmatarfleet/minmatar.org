import { expect, within } from 'storybook/test'
import BuybackContractsTable from '@components/blocks/BuybackContractsTable.astro'
import { buyback_history, buyback_mixed } from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Industry/BuybackContractsTable',
    component: BuybackContractsTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'The ledger of item-exchange contracts members have made to the Minmatar Extraction Company buyback, at `/market/buyback/contracts/` and its history page. Each row shows who created it, where, its status (outstanding, in progress, finished), size, price, description and who accepted it.',
                    'A description that is a URL becomes a link; a blank one shows a dash. Outside history a button leads to all historical contracts. Scenarios show an empty ledger, a mix of statuses, and a long history list.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        contracts: { control: 'object', description: '`BuybackContract[]`, newest first.' },
        is_history: { control: 'boolean', description: 'Hides the "View all historical contracts" button.' },
    },
    args: { contracts: buyback_mixed, is_history: false },
}

export const MixedStatuses = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('table')).toBeInTheDocument()
        await expect(canvas.getAllByRole('columnheader')).toHaveLength(8)
        // Header row + 4 contracts.
        await expect(canvas.getAllByRole('row')).toHaveLength(5)
        await expect(canvas.getByText('Outstanding')).toBeVisible()
        await expect(canvas.getByText('In progress')).toBeVisible()
        await expect(canvas.getAllByText('Recently completed')).toHaveLength(2)
        await expect(canvas.getByText('Hurricane Fleet Issue hulls and fits')).toBeVisible()
        await expect(canvas.getByText('184,500,000')).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'View all historical contracts' })).toHaveAttribute('href', '/market/buyback/contracts/history/')
    },
}

export const DescriptionLinkAndBlank = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const link = canvas.getByRole('link', { name: 'Link' })
        await expect(link).toHaveAttribute('href', 'https://my.minmatar.org/market/buyback/appraisal/9aK2p/')
        await expect(link).toHaveAttribute('target', '_blank')
        await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
        // Blank description: a dash.
        await expect(canvas.getAllByText('—').length).toBeGreaterThan(0)
    },
}

export const Empty = {
    args: { contracts: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('columnheader')).toHaveLength(8)
        await expect(canvas.queryAllByRole('row')).toHaveLength(1)
        await expect(canvas.getByRole('link', { name: 'View all historical contracts' })).toBeVisible()
    },
}

export const History = {
    args: { contracts: buyback_history, is_history: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(15)
        await expect(canvas.queryByRole('link', { name: 'View all historical contracts' })).toBeNull()
        await expect(canvas.queryByText('Outstanding')).toBeNull()
    },
}
