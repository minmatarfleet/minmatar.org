import { expect, within } from 'storybook/test'
import Tile from '@components/blocks/Tile.astro'
import Button from '@components/blocks/Button.astro'
import Badge from '@components/blocks/Badge.astro'
import FlagIcon from '@components/icons/FlagIcon.astro'
import { space_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Data display/Tile',
    component: Tile,
    parameters: {
        docs: {
            description: {
                component: [
                    'A cover-image panel for landing pages and catalogues: the picture fills the tile and fades out towards the bottom, with the title, an inline-Markdown description and actions laid over it.',
                    'Use it for entry points to a section ("Browse orders", a tribe group). Use `Card` / `PictureCard` for picture-first grids with hover actions, and `ComponentBlock` for a plain bordered panel.',
                    '`min_height` and `gap` are raw CSS strings (they feed an inline style). `optimize` routes the cover through `astro:assets`, which needs a bundler-known path, so leave it off for `/images/*` public files.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        title: { control: 'text', description: 'Heading (h2) and the default image alt text.' },
        description: { control: 'text', description: 'Inline Markdown shown under the title (max 380px wide).' },
        cover: { control: 'text', description: 'Image URL; rendered as an absolutely positioned, masked `<img>`.' },
        alt: { control: 'text', description: 'Alt text for the cover; falls back to `title`.' },
        transparent: { control: 'boolean', description: 'Drop the border and light-transparency glass, leaving only the picture.' },
        soft: { control: 'boolean', description: 'Weaker top of the fade mask so the picture sits further back.' },
        optimize: { control: 'boolean', description: 'Render the cover with astro:assets `<Image>` (webp, `width` x `height`).' },
        width: { control: 'number', description: 'Optimised image width (only with `optimize`).' },
        height: { control: 'number', description: 'Optimised image height (only with `optimize`).' },
        gap: space_control('Space between the heading block and the description / actions.'),
        min_height: { control: 'text', description: 'Minimum body height as a CSS length; keeps tiles in a grid the same size.' },
    },
    args: {
        title: 'Industry orders',
        description: 'Request **ships and modules** built by the alliance industrialists, paid on delivery.',
        cover: '/images/buyback-cover.jpg',
        transparent: false,
        soft: true,
        optimize: false,
        width: 512,
        height: 512,
        gap: 'var(--space-s)',
        min_height: '420px',
        slots: {
            default: { component: Button, props: { size: 'sm', href: '/industry/orders/' }, slots: { default: 'Browse' } },
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const tile = canvasElement.querySelector('.tile') as HTMLElement
        await expect(tile).toHaveClass('card', 'component', 'border', 'light-transparency', 'soft')
        await expect(canvas.getByRole('heading', { level: 2, name: 'Industry orders' })).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'Browse' })).toHaveAttribute('href', '/industry/orders/')
        const cover = canvas.getByRole('img', { name: 'Industry orders' })
        await expect(cover).toHaveAttribute('src', '/images/buyback-cover.jpg')
        await expect(tile.querySelector('.tile__body')?.getAttribute('style')).toContain('min-height: 420px')
    },
}

export const MarkdownDescription = {
    args: {
        title: 'Rattini Tribe',
        description: 'The **A-RAT** corporation: frigates, [fleet doctrines](/doctrines/) and a *lot* of kiting.',
        cover: '/images/alliance-cover.jpg',
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('A-RAT').tagName).toBe('STRONG')
        await expect(canvas.getByRole('link', { name: 'fleet doctrines' })).toHaveAttribute('href', '/doctrines/')
    },
}

export const Transparent = {
    args: { transparent: true },
    play: async ({ canvasElement }: Ctx) => {
        const tile = canvasElement.querySelector('.tile') as HTMLElement
        await expect(tile).not.toHaveClass('border')
        await expect(tile).not.toHaveClass('light-transparency')
    },
}

export const Sharp = {
    name: 'Not soft',
    args: { soft: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('.tile')).not.toHaveClass('soft')
    },
}

export const WithIconAndSubtitle = {
    name: 'With icon, subtitle and several actions',
    args: {
        title: 'Strategic fleets',
        description: 'Fleets run by the alliance FCs to push the Amarr back.',
        cover: '/images/alliance-cover.jpg',
        slots: {
            icon: { component: FlagIcon },
            subtitle: { component: Badge, props: { color: 'alliance-blue' }, slots: { default: '3 upcoming' } },
            default: [
                { component: Button, props: { size: 'sm', href: '/fleets/upcoming/' }, slots: { default: 'Upcoming' } },
                { component: Button, props: { size: 'sm', color: 'transparent', href: '/fleets/history/' }, slots: { default: 'History' } },
            ],
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const tile = canvasElement.querySelector('.tile') as HTMLElement
        await expect(tile.querySelector('svg')).not.toBeNull()
        await expect(canvas.getByText('3 upcoming')).toBeVisible()
        await expect(canvas.getAllByRole('link')).toHaveLength(2)
    },
}

export const NoActions = {
    name: 'No actions',
    args: { slots: {} },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Industry orders' })).toBeVisible()
        await expect(canvas.queryByRole('link')).toBeNull()
    },
}

export const CustomAlt = {
    args: { alt: 'Industrialists loading a hauler at the station', min_height: '24rem', gap: 'var(--space-xs)' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('img', { name: 'Industrialists loading a hauler at the station' })).toBeVisible()
        await expect(canvasElement.querySelector('.tile__body')?.getAttribute('style')).toContain('min-height: 24rem')
    },
}

export const Passthrough = {
    name: 'Attributes reach the root',
    args: { 'data-testid': 'doctrine-tile', 'x-data': '{ open: false }' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // Extra attributes used to be collected and dropped.
        const tile = within(canvasElement).getByTestId('doctrine-tile')
        await expect(tile).toHaveClass('tile')
        await expect(tile).toHaveAttribute('x-data', '{ open: false }')
    },
}
