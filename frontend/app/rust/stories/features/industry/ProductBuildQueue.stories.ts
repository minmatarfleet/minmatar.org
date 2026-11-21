import { expect, within } from 'storybook/test'
import ProductBuildQueue from '@components/blocks/ProductBuildQueue.astro'
import { insights_all_claimed, insights_busy, insights_idle } from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Industry/ProductBuildQueue',
    component: ProductBuildQueue,
    parameters: {
        docs: {
            description: {
                component: [
                    'Two panels on the product Build tab (`/industry/products/<id>/build/`): "Needed now" lists the open orders for the product with the ones missing a builder first and a Claim button each, and "Running now" lists the jobs pilots have in production with when they finish.',
                    'It reads the cached `ProductInsights` rollup. Scenarios show a busy queue with four stages of order, a fully claimed queue, and nothing open or running.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        insights: { control: 'object', description: 'The `ProductInsights` rollup; the queue reads `orders.recent`, `orders.open_*`, `running` and `built.running_*`.' },
    },
    args: { insights: insights_busy },
}

export const BusyQueue = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Needed now' })).toBeVisible()
        // The fulfilled order is left out; four are open.
        await expect(canvas.getAllByRole('link', { name: /^#/ })).toHaveLength(4)
        await expect(canvas.queryByRole('link', { name: /Q9L1C/ })).toBeNull()
        await expect(canvas.getByText('31 without a builder')).toBeVisible()
        // Most unclaimed first.
        const links = canvas.getAllByRole('link', { name: /^#/ })
        await expect(links[0]).toHaveTextContent('#KX4T9')
        await expect(links[0]).toHaveAttribute('href', '/industry/orders/8412/')
        await expect(canvas.getByRole('link', { name: 'Claim 20' })).toHaveAttribute('href', '/industry/orders/8412/')
    },
}

export const FullyClaimedOrderReadsView = {
    args: { insights: insights_busy },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        // B8WZ2 has all 30 claimed: nothing to claim, so the button is a quiet "View".
        const view = canvas.getByRole('link', { name: 'View' })
        await expect(view).toHaveAttribute('href', '/industry/orders/8397/')
        await expect(canvas.getByText(/\d+ ordered, 12 delivered, 18 being built/)).toBeVisible()
        await expect(canvas.getByText(/No date · 8 ordered, 0 delivered, 2 being built/)).toBeVisible()
    },
}

export const RunningJobs = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Running now' })).toBeVisible()
        await expect(canvas.getByText('22 units in 4 jobs')).toBeVisible()
        await expect(canvas.getAllByText(/^Done /)).toHaveLength(4)
        await expect(canvas.getByText('1 unit')).toBeVisible()
        await expect(canvas.getByText('12 units')).toBeVisible()
        await expect(canvas.getByText(/Auga Hauler/)).toBeVisible()
    },
}

export const AllClaimed = {
    args: { insights: insights_all_claimed },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.queryByText(/without a builder/)).toBeNull()
        await expect(canvas.getAllByRole('link', { name: 'View' })).toHaveLength(2)
        await expect(canvas.queryByRole('link', { name: /^Claim/ })).toBeNull()
    },
}

export const NothingOpenOrRunning = {
    args: { insights: insights_idle },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No open orders for this right now.')).toBeVisible()
        await expect(canvas.getByText('Nothing in production right now.')).toBeVisible()
        await expect(canvas.queryByText(/without a builder/)).toBeNull()
    },
}
