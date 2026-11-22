import { expect, within } from 'storybook/test'
import PictureCard from '@components/blocks/PictureCard.astro'
import Button from '@components/blocks/Button.astro'
import Badge from '@components/blocks/Badge.astro'
import { EVE } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

const portrait = `https://images.evetech.net/characters/${EVE.character_id}/portrait?size=256`

export default {
    title: 'Components/Data display/PictureCard',
    component: PictureCard,
    parameters: {
        docs: {
            description: {
                component: [
                    'A picture card (the internal `Card` on `ComponentBlock`, not a library component of its own) whose cover is a masked `Picture` at 256px: portraits, ship renders, screenshots. It forwards the `header`, `actions` and default slots to the card, so overlays work as they do there (actions fade in on hover).',
                    '`narrow` makes the picture tall (412px) for portrait art, `thumbnail` crops to the shared thumbnail aspect ratio so reels line up, and `zoomable` opens the full image in a lightbox on click.',
                    'Passing `astro_image` renders through `astro:assets` instead of a plain `<img>`; it needs a bundler-known source, so it is not demoed here. Other attributes pass to the underlying `Card`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        src: { control: 'text', description: 'Image URL.' },
        alt: { control: 'text', description: 'Alt text; omitted when empty (decorative).' },
        narrow: { control: 'boolean', description: 'Tall 412px picture instead of a square one.' },
        zoomable: { control: 'boolean', description: 'Click opens the image in a zoom overlay.' },
        thumbnail: { control: 'boolean', description: 'Crop to the fixed thumbnail aspect ratio.' },
        astro_image: { control: 'object', description: 'astro:assets `<Image>` options; switches to optimised rendering.' },
    },
    args: {
        src: portrait,
        alt: EVE.character_name,
        narrow: false,
        zoomable: false,
        thumbnail: false,
        slots: { default: `<strong>${EVE.character_name}</strong>` },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const img = canvas.getByRole('img', { name: EVE.character_name })
        await expect(img).toHaveAttribute('src', portrait)
        await expect(img).toHaveAttribute('width', '256')
        await expect(img).toHaveAttribute('height', '256')
        await expect(img).toHaveClass('mask')
        await expect(canvasElement.querySelector('.card')).not.toBeNull()
        await expect(canvasElement.querySelector('.card-body')).toHaveTextContent(EVE.character_name)
    },
}

export const Narrow = {
    args: { narrow: true },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('img')).toHaveAttribute('height', '412')
    },
}

export const Thumbnail = {
    args: { thumbnail: true, src: '/images/alliance-cover.jpg', alt: 'Alliance cover', slots: { default: '<strong>Fleet briefing</strong>' } },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Alliance cover' })
        await expect(img).toHaveClass('thumbnail-fill')
        await expect(canvasElement.querySelector('picture')).toHaveClass('fixed-thumbnail')
    },
}

export const Zoomable = {
    args: { zoomable: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('img', { name: EVE.character_name })).toBeInTheDocument()
        await expect(canvasElement.querySelector('picture')).not.toHaveClass('fixed-thumbnail')
    },
}

export const WithHeaderAndActions = {
    name: 'With header and actions',
    args: {
        slots: {
            header: { component: Badge, props: { color: 'alliance-blue' }, slots: { default: 'FC' } },
            default: `<strong>${EVE.character_name}</strong><br /><small>${EVE.corporation_name}</small>`,
            actions: { component: Button, props: { size: 'sm', href: '/pilots/' }, slots: { default: 'Open pilot' } },
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(within(canvasElement.querySelector('.card-header') as HTMLElement).getByText('FC')).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'Open pilot' })).toHaveAttribute('href', '/pilots/')
        await expect(canvas.getByText(EVE.corporation_name)).toBeVisible()
    },
}

export const ShipRender = {
    name: 'Ship render',
    args: {
        src: `https://images.evetech.net/types/${EVE.rifter_type_id}/render?size=256`,
        alt: EVE.rifter_name,
        slots: { default: `<strong>${EVE.rifter_name}</strong><br /><small>Frigate · Minmatar</small>` },
    },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: EVE.rifter_name })
        await expect(img.getAttribute('src')).toContain(`/types/${EVE.rifter_type_id}/render`)
    },
}

export const Decorative = {
    name: 'No alt (decorative)',
    args: { alt: undefined },
    play: async ({ canvasElement }: Ctx) => {
        const img = canvasElement.querySelector('picture img') as HTMLElement
        await expect(img).not.toHaveAttribute('alt')
    },
}
