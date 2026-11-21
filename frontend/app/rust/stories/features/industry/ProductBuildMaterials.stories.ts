import { expect, within } from 'storybook/test'
import ProductBuildMaterials from '@components/blocks/ProductBuildMaterials.astro'
import {
    build_hurricane,
    build_missing_prices,
    build_no_materials,
    build_rifter,
    build_wolf,
} from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Industry/ProductBuildMaterials',
    component: ProductBuildMaterials,
    parameters: {
        docs: {
            description: {
                component: [
                    'The bill of materials on the product Build tab (`/industry/products/<id>/build/`): one row per input with quantity, unit price, line cost and where the supply chain gets it, plus the per-run total.',
                    'A material that is itself an industry product links to its own page and carries a strategy tag (built in-house, harvested, imported); anything else reads "Not tracked". Scenarios show a long list, a short one, a chain (Wolf is built from a Rifter), missing prices and an empty list.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        build: { control: 'object', description: 'The `ProductBuild`; only `materials` and `material_cost` are read here.' },
    },
    args: { build: build_hurricane },
}

export const SevenMaterials = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Bill of materials' })).toBeVisible()
        await expect(canvas.getByText('7 materials per run, 6 tracked in our supply chain')).toBeVisible()
        // Header row + 7 materials + the total row.
        await expect(canvas.getAllByRole('row')).toHaveLength(9)
        await expect(canvas.getByRole('rowheader', { name: /Tritanium/ })).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'Tritanium' })).toHaveAttribute('href', '/industry/products/3001/')
        await expect(canvas.getByText('Total per run')).toBeVisible()
    },
}

export const Strategies = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByText('Harvested').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('Imported').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('Built in-house').length).toBeGreaterThan(0)
        // Megacyte has no strategy.
        await expect(canvas.getAllByText('Not tracked')).toHaveLength(1)
        // Mineral unit prices keep their cents.
        await expect(canvas.getByText('4.10')).toBeVisible()
    },
}

export const ShortList = {
    args: { build: build_rifter },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('4 materials per run, 4 tracked in our supply chain')).toBeVisible()
        await expect(canvas.getAllByRole('row')).toHaveLength(6)
        // Isogen has no product page: plain text, not a link.
        await expect(canvas.queryByRole('link', { name: 'Isogen' })).toBeNull()
    },
}

export const BuiltFromAnotherProduct = {
    args: { build: build_wolf },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Rifter' })).toHaveAttribute('href', '/industry/products/4001/')
        await expect(canvas.getByText('Nocxium')).toBeVisible()
    },
}

export const MissingPrices = {
    args: { build: build_missing_prices },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        // Zydrine and Megacyte have no price: unit price and line cost read "—".
        await expect(canvas.getAllByText('—').length).toBeGreaterThanOrEqual(4)
    },
}

export const Empty = {
    args: { build: build_no_materials },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No materials listed for this blueprint.')).toBeVisible()
        await expect(canvas.queryByRole('table')).toBeNull()
    },
}
