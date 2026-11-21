import { expect, within } from 'storybook/test'
import ProductBuildCost from '@components/blocks/ProductBuildCost.astro'
import {
    build_batch,
    build_hurricane,
    build_loss_making,
    build_missing_prices,
    build_rifter,
    build_wolf,
} from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

const planner_path = '/industry/orders/planner/?product=4002'

export default {
    title: 'Features/Industry/ProductBuildCost',
    component: ProductBuildCost,
    parameters: {
        docs: {
            description: {
                component: [
                    'The "Is it worth building?" panel on the product Build tab (`/industry/products/<id>/build/`): what one run sells for, what its materials cost, the margin and the build time, with a button into the order planner.',
                    'Scenarios cover a profitable run, a loss, unknown prices (the margin shows a dash and a hint), a T2 hull whose margin already includes invention, and a batch product that makes many units per run.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        build: { control: 'object', description: 'The `ProductBuild` for one run at Jita sell prices (base SDE quantities, no ME/TE).' },
        planner_path: { control: 'text', description: 'Where "Open in planner" points.' },
    },
    args: { build: build_hurricane, planner_path },
}

export const Profitable = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Is it worth building?' })).toBeVisible()
        await expect(canvas.getByText('One run at Jita sell prices')).toBeVisible()
        await expect(canvas.getByText('Sells for')).toBeVisible()
        await expect(canvas.getByText('3d 4h')).toBeVisible()
        await expect(canvasElement.querySelector('dd.is-good')).not.toBeNull()
        await expect(canvasElement.querySelector('dd.is-bad')).toBeNull()
        await expect(canvas.getByText(/Base blueprint numbers: no material or time efficiency/)).toBeVisible()
        await expect(canvas.getByRole('link', { name: /Open in planner/ })).toHaveAttribute('href', planner_path)
    },
}

export const SingleHull = {
    args: { build: build_rifter },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('1h 40m')).toBeVisible()
        await expect(canvasElement.querySelector('dd.is-good')).not.toBeNull()
    },
}

export const LossMaking = {
    args: { build: build_loss_making },
    play: async ({ canvasElement }: Ctx) => {
        const margin = canvasElement.querySelector('dd.is-bad')
        await expect(margin).not.toBeNull()
        await expect(margin?.textContent).toMatch(/^\s*-/)
        await expect(canvasElement.querySelector('dd.is-good')).toBeNull()
    },
}

export const MissingPrices = {
    args: { build: build_missing_prices },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Some materials have no market price yet, so the margin is unknown.')).toBeVisible()
        // Materials and margin both read "—", and the partial total is dimmed.
        await expect(canvas.getAllByText('—')).toHaveLength(2)
        await expect(canvasElement.querySelector('dd.is-partial')).not.toBeNull()
    },
}

export const WithInvention = {
    args: { build: build_wolf },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/The margin takes off .* of expected invention for the run\./)).toBeVisible()
        await expect(canvas.getByText('2d 2h')).toBeVisible()
    },
}

export const BatchProduct = {
    args: { build: build_batch },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('One run (100 units) at Jita sell prices')).toBeVisible()
        await expect(canvas.getByText('25m')).toBeVisible()
    },
}
