import { expect, within } from 'storybook/test'
import ItemPicture from '@components/blocks/ItemPicture.astro'
import { select_control, EVE } from '../_controls'

const SIZES = [16, 24, 32, 64, 128, 256, 512, 1024] as const
const QUALITIES = [32, 64, 128, 256, 512, 1024] as const

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'EVE/ItemPicture',
    component: ItemPicture,
    parameters: {
        docs: {
            description: {
                component: [
                    'An EVE type icon (or, from 128px up, a ship render) from the image server. Use it for hulls, modules and blueprints in fit lists, order rows and doctrine cards; pair it with `ItemBadge` when a name belongs next to it.',
                    'Icon qualities up to 64 request `/icon`; larger ones request `/render`. Pass `blueprint` to request the blueprint original or copy artwork (`/bp` or `/bpc`) instead. `quantity` adds a corner count.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        item_id: { control: 'number', description: 'EVE type id.' },
        item_name: { control: 'text', description: 'Alt text. Falls back to "Item picture".' },
        size: select_control(SIZES, 'Rendered width in px.'),
        narrow: { control: 'boolean', description: 'Tall crop (height 412).' },
        icon_quality: select_control(QUALITIES, 'Image-server size requested. Up to 64 is an icon, above is a render.'),
        mask: { control: 'boolean', description: 'Fade the bottom out with a gradient mask.' },
        quantity: { control: 'number', description: 'Shows a corner count badge.' },
        blueprint: { control: 'object', description: '`{ is_copy }`: show blueprint original (`bp`) or copy (`bpc`) artwork.' },
    },
    args: {
        item_id: EVE.rifter_type_id,
        item_name: EVE.rifter_name,
        size: 64,
        narrow: false,
        icon_quality: 64,
        mask: false,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Rifter' })
        await expect(img).toHaveAttribute('src', 'https://images.evetech.net/types/587/icon?size=64')
        await expect(img).toHaveAttribute('width', '64')
        await expect(img).toHaveAttribute('height', '64')
        await expect(img.closest('picture')).toHaveClass('animated')
    },
}

export const ShipRender = {
    args: { item_id: EVE.stabber_type_id, item_name: EVE.stabber_name, size: 256, icon_quality: 256 },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Stabber' })
        await expect(img).toHaveAttribute('src', 'https://images.evetech.net/types/622/render?size=256')
    },
}

export const BlueprintOriginal = {
    args: { item_id: 691, item_name: 'Rifter Blueprint', blueprint: { is_copy: false } },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Rifter Blueprint' })
        await expect(img).toHaveAttribute('src', 'https://images.evetech.net/types/691/bp?size=64')
    },
}

export const BlueprintCopy = {
    args: { item_id: 691, item_name: 'Rifter Blueprint (copy)', blueprint: { is_copy: true } },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img).toHaveAttribute('src', 'https://images.evetech.net/types/691/bpc?size=64')
    },
}

export const WithQuantity = {
    args: { item_id: 34, item_name: 'Tritanium', quantity: 1250000 },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('img', { name: 'Tritanium' })).toBeVisible()
        await expect(canvas.getByText('1.3M')).toBeVisible()
    },
}

export const MaskedNarrow = {
    args: { size: 256, icon_quality: 512, narrow: true, mask: true },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img).toHaveClass('mask')
        await expect(img).toHaveAttribute('height', '412')
    },
}

export const NoName = {
    args: { item_name: undefined },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('img', { name: 'Item picture' })).toBeVisible()
    },
}

export const ZeroQuantity = {
    name: 'Zero quantity shows no badge',
    args: { item_id: 34, item_name: 'Tritanium', quantity: 0 },
    play: async ({ canvasElement }: Ctx) => {
        // `{quantity && ...}` used to print a literal 0 beside the icon.
        await expect(canvasElement.querySelector('.quantity-badge')).toBeNull()
        await expect(canvasElement.querySelector('picture')?.textContent?.trim()).toBe('')
    },
}
