import { expect, within } from 'storybook/test'
import ProductsList from '@components/blocks/ProductsList.astro'
import { products_list } from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

// The products page's Alpine scope: a search filter and the visible-row count.
const PageScope = (story: () => unknown) =>
    `<div x-data="{ products_count: ${products_list.length}, show_item() { return true } }">${story()}</div>`

export default {
    title: 'Features/Industry/ProductsList',
    component: ProductsList,
    decorators: [PageScope],
    parameters: {
        docs: {
            description: {
                component: [
                    'The list of supply-chain products at `/industry/products/`: one `ProductItem` row per product, minerals and hulls alike, with a "no products" message the page reveals when the search box matches nothing.',
                    'Scenarios show the full list, a single product, and an empty list (the page sets `products_count` to zero, which shows the message).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        products: { control: 'object', description: '`Product[]` from the products API.' },
    },
    args: { products: products_list },
}

export const FullList = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('a.product-item')).toHaveLength(products_list.length)
        await expect(canvas.getByRole('heading', { name: 'Hurricane' })).toBeVisible()
        await expect(canvas.getByRole('heading', { name: 'Tritanium' })).toBeVisible()
        await expect(canvasElement.querySelector('a[href="/industry/products/3001/"]')).not.toBeNull()
        // Hidden while products_count is non-zero.
        await expect(canvas.getByText('No products to display.')).not.toBeVisible()
    },
}

export const SingleProduct = {
    args: { products: [products_list[0]] },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('a.product-item')).toHaveLength(1)
    },
}

export const Empty = {
    args: { products: [] },
    decorators: [(story: () => unknown) => `<div x-data="{ products_count: 0, show_item() { return true } }">${story()}</div>`],
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('a.product-item')).toHaveLength(0)
        await expect(canvas.getByText('No products to display.')).toBeVisible()
    },
}
