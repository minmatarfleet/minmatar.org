import { expect, within } from 'storybook/test'
import ItemBadge from '@components/blocks/ItemBadge.astro'
import { select_control, EVE } from '../_controls'

const QUALITIES = [32, 64, 128, 256, 512, 1024] as const

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'EVE/ItemBadge',
    component: ItemBadge,
    parameters: {
        docs: {
            description: {
                component: [
                    'An EVE type icon with its name beside it, for hulls, modules and materials in fit lists, orders and SRP rows. A thin wrapper over `Badge` that builds the image-server URL from `type_id`.',
                    '`size` is both the icon width and the image-server size requested. With no default slot content, `quantity` renders as a thousand-separated number under the name; slot content replaces it. The `title` slot adds inline content after the name. Extra attributes pass through to the layout wrapper.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        item_name: { control: 'text', description: 'Name shown beside the icon.' },
        type_id: { control: 'number', description: 'EVE type id.' },
        size: select_control(QUALITIES, 'Icon width in px and image-server size requested.'),
        border: { control: 'boolean', description: 'Border around the icon.' },
        highlight: { control: 'boolean', description: 'Colour the name with `--highlight`.' },
        title_el: select_control(['span', 'h3', 'h4', 'p'], 'Element the name renders as.'),
        quantity: { control: 'number', description: 'Shown under the name, thousand-separated, when the slot is empty.' },
    },
    args: {
        item_name: EVE.rifter_name,
        type_id: EVE.rifter_type_id,
        size: 64,
        border: false,
        highlight: true,
        title_el: 'span',
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Rifter')).toBeVisible()
        const img = canvasElement.querySelector('img') as HTMLElement
        await expect(img).toHaveAttribute('src', 'https://images.evetech.net/types/587/icon?size=64')
        await expect(img).toHaveAttribute('width', '64')
        await expect(canvas.getByText('Rifter').className).toContain('text-highlight')
    },
}

export const WithQuantity = {
    args: { item_name: 'Tritanium', type_id: 34, quantity: 1250000 },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Tritanium')).toBeVisible()
        await expect(canvas.getByText(/1.250.000|1,250,000|1 250 000/)).toBeVisible()
    },
}

export const SlotReplacesQuantity = {
    args: { item_name: EVE.stabber_name, type_id: EVE.stabber_type_id, quantity: 20, slots: { default: '<small>Cruiser · Doctrine hull</small>' } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Cruiser · Doctrine hull')).toBeVisible()
        await expect(canvas.queryByText('20')).toBeNull()
    },
}

export const TitleSlot = {
    args: { slots: { title: '<span class="tag">Fitted</span>' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('Fitted')).toBeVisible()
    },
}

export const Small = {
    args: { size: 32, item_name: 'Warrior II', type_id: 2488 },
    play: async ({ canvasElement }: Ctx) => {
        const img = canvasElement.querySelector('img') as HTMLElement
        await expect(img).toHaveAttribute('width', '32')
        await expect(img).toHaveAttribute('src', 'https://images.evetech.net/types/2488/icon?size=32')
    },
}

export const BorderedHeading = {
    args: { border: true, title_el: 'h3', highlight: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('picture')).toHaveClass('border')
        await expect(within(canvasElement).getByRole('heading', { level: 3, name: /Rifter/ })).toBeVisible()
    },
}
