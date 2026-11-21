import { expect, within } from 'storybook/test'
import TypeRow from '@components/blocks/sde/TypeRow.astro'
import { module_type, ship } from './_fixtures'

type Ctx = { canvasElement: HTMLElement }

const row = (canvasElement: HTMLElement) => canvasElement.querySelector('.type-row') as HTMLElement

export default {
    title: 'EVE/SDE/TypeRow',
    component: TypeRow,
    parameters: {
        docs: {
            description: {
                component: [
                    'One inventory type in a list: icon, name, MetaGroupTag and "Group · Category", plus the hull\'s ShipSlots with `show_slots`. It is the row TypeResults renders; reach for ItemBadge instead when you only have a name and an id (fit lists, orders with quantities).',
                    'Icons come from images.evetech.net; a `size` above 64 asks for the ship render. The image is decorative (`alt=""`) because the name sits beside it. `href` turns the whole row into a link. The type comes in as a prop (`search_types()` returns this shape); the component never queries the SDE.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        type: { control: 'object', description: '`SdeType`: id, name, group, category, meta group, and `slots` for hulls.' },
        href: { control: 'text', description: 'Link the row to this page.' },
        size: { control: 'select', options: [32, 48, 64, 128], description: 'Icon width in px; above 64 shows the render.' },
        show_group: { control: 'boolean', description: 'Show "Group · Category" under the name.' },
        show_meta: { control: 'boolean', description: 'Show the meta group tag after the name.' },
        show_slots: { control: 'boolean', description: 'Show the slot layout (ships with `type.slots`).' },
    },
    args: {
        type: ship('Rifter'),
        size: 32,
        show_group: true,
        show_meta: true,
        show_slots: false,
    },
}

export const Default = {
    name: 'Ship (Rifter)',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Rifter')).toBeVisible()
        await expect(canvas.getByText('Frigate · Ship')).toBeVisible()
        await expect(canvas.getByText('Tech I')).toBeVisible()
        const img = canvasElement.querySelector('img') as HTMLImageElement
        await expect(img).toHaveAttribute('src', 'https://images.evetech.net/types/587/icon?size=64')
        await expect(img).toHaveAttribute('width', '32')
        await expect(img).toHaveAttribute('alt', '')
        await expect(row(canvasElement)).toHaveAttribute('data-type-id', '587')
        await expect(row(canvasElement)).toHaveAttribute('data-category-id', '6')
    },
}

export const WithSlots = {
    name: 'Hull with slots (Vagabond)',
    args: { type: ship('Vagabond'), size: 64, show_slots: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Heavy Assault Cruiser · Ship')).toBeVisible()
        await expect(canvas.getByText('Tech II')).toBeVisible()
        await expect(canvas.getByRole('list', { name: 'Slot layout' })).toBeVisible()
        await expect(canvasElement.querySelector('[data-slot="high"]')).toHaveAttribute('data-count', '6')
    },
}

export const Module = {
    name: 'Module (Gyrostabilizer II)',
    args: { type: module_type('Gyrostabilizer II') },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Gyrostabilizer · Module')).toBeVisible()
        await expect(canvasElement.querySelector('.meta-group-tag')).toHaveAttribute('data-meta-group', 'tech-ii')
    },
}

export const Officer = {
    name: "Officer module (Tobias')",
    args: { type: module_type("Tobias' Modified Heavy Warp Scrambler") },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText("Tobias' Modified Heavy Warp Scrambler")).toBeVisible()
        await expect(canvasElement.querySelector('.meta-group-tag')).toHaveAttribute('data-meta-group', 'officer')
    },
}

export const Linked = {
    args: { type: ship('Hurricane Fleet Issue'), href: '/ships/fittings/?ship=Hurricane%20Fleet%20Issue' },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link', { name: /Hurricane Fleet Issue/ })
        await expect(link).toHaveAttribute('href', '/ships/fittings/?ship=Hurricane%20Fleet%20Issue')
        await expect(link).toHaveClass('type-row')
    },
}

export const ShipRender = {
    name: 'Large render (Tempest)',
    args: { type: ship('Tempest'), size: 128, show_slots: true },
    play: async ({ canvasElement }: Ctx) => {
        const img = canvasElement.querySelector('img') as HTMLImageElement
        await expect(img).toHaveAttribute('src', 'https://images.evetech.net/types/639/render?size=256')
        await expect(img).toHaveAttribute('width', '128')
    },
}

export const NameOnly = {
    name: 'Name only (no group, no meta)',
    args: { type: module_type('Gistii B-Type 5MN Microwarpdrive'), show_group: false, show_meta: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('Gistii B-Type 5MN Microwarpdrive')).toBeVisible()
        await expect(canvasElement.querySelector('.meta-group-tag')).toBeNull()
        await expect(canvasElement.querySelector('.type-row__group')).toBeNull()
    },
}
