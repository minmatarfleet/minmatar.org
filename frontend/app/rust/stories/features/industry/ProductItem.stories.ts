import { expect, within } from 'storybook/test'
import ProductItem from '@components/blocks/ProductItem.astro'
import {
    product_final_hull,
    product_imported_many_parents,
    product_mineral,
} from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

// The products page's Alpine scope: each row asks `show_item($el)` whether it matches the search box.
const PageScope = (story: () => unknown) =>
    `<div x-data="{ show_item() { return true } }">${story()}</div>`

export default {
    title: 'Features/Industry/ProductItem',
    component: ProductItem,
    decorators: [PageScope],
    parameters: {
        docs: {
            description: {
                component: [
                    'One product in the supply-chain list at `/industry/products/`: its icon and name, its strategy (built in-house, harvested or imported, imported shown in red), a blueprint icon when it has one, and the parents it goes into. The whole row links to the product page `/industry/products/<id>/`.',
                    'Scenarios show a final product with no parents, a material used in a few hulls, and an import used in more hulls than fit (the rest collapse to "+N").',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        product: { control: 'object', description: 'The `Product`: type, strategy, blueprint or reaction id and `supplied_for` parents.' },
    },
    args: { product: product_final_hull },
}

export const FinalProduct = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const link = canvasElement.querySelector('a.product-item')
        await expect(link).toHaveAttribute('href', '/industry/products/4002/')
        await expect(canvas.getByRole('heading', { name: 'Hurricane' })).toBeVisible()
        await expect(canvas.getByText('Final product')).toBeVisible()
        await expect(canvas.queryByText('Used in')).toBeNull()
        await expect(canvas.getByText(/Details/)).toBeInTheDocument()
    },
}

export const UsedInAFewHulls = {
    args: { product: product_mineral },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Used in')).toBeVisible()
        for (const name of ['Rifter', 'Hurricane', 'Wolf'])
            await expect(canvas.getByText(name)).toBeInTheDocument()
        await expect(canvas.queryByText(/^\+\d/)).toBeNull()
        await expect(canvas.getByText('Harvested')).toBeVisible()
    },
}

export const ImportedUsedInMany = {
    args: { product: product_imported_many_parents },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const imported = canvas.getByText('Imported')
        await expect(imported).toHaveClass('text-red')
        // Eight parents, six icons, the rest summarised.
        await expect(canvas.getByText('+2')).toBeVisible()
        await expect(canvas.queryByText('Vagabond')).toBeNull()
    },
}
