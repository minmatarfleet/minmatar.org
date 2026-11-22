import { expect, within } from 'storybook/test'
import Picture from '@components/blocks/Picture.astro'
import { select_control } from '../_controls'

const SRC = 'https://images.evetech.net/types/587/render?size=512'
const SIZES = [16, 24, 32, 64, 128, 256, 512, 1024] as const

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'EVE/Picture',
    component: Picture,
    parameters: {
        docs: {
            description: {
                component: [
                    'A generic lazy-loaded `<picture>` + `<img>` for any image URL (posts, doctrine renders, thumbnails). For EVE portraits, logos and item icons use `CharacterPicture`, `CorporationPicture` and `ItemPicture`: they build the image-server URL from an id (`@helpers/eve_image`) and render through this component, so the mask and the quantity badge are defined once.',
                    '`quantity` adds a count badge on the bottom-right corner (`tag_color` picks its colour); `target` wraps the image in a link, button or span (its `attrs` go on that element); `brighten` lights the image on hover; `img_attrs` adds attributes such as Alpine `x-bind:src` to the `<img>`. Other attributes go to the `<picture>`.',
                    '`size` sets the `width` attribute; `height` follows `size` unless `narrow` is set (then 412). `zoomable` swaps the `<img>` for `ZoomableImage` (medium-zoom lightbox). `thumbnail` crops to a shared 3:4 ratio so reels and cards line up. `placeholder` is swapped in through an inline `onerror` if the image fails.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        src: { control: 'text', description: 'Image URL.' },
        alt: { control: 'text', description: 'Alt text. Omitted from the markup when empty (decorative image).' },
        size: select_control(SIZES, 'Image `width` in px; also the height unless `narrow`.'),
        narrow: { control: 'boolean', description: 'Tall crop: height 412 regardless of `size`.' },
        mask: { control: 'boolean', description: 'Fade the bottom of the image out with a gradient mask.' },
        zoomable: { control: 'boolean', description: 'Click to open the image in a zoom lightbox.' },
        placeholder: { control: 'text', description: 'URL swapped in when the image fails to load.' },
        thumbnail: { control: 'boolean', description: 'Crop to a shared 3:4 aspect ratio (`fixed-thumbnail`).' },
        quantity: { control: 'number', description: 'Count shown in a badge on the picture.' },
        tag_color: { control: 'text', description: 'Badge colour token (default `fleet-red`).' },
        brighten: { control: 'boolean', description: 'Brighten the image on hover.' },
        astro_image: { control: 'object', description: 'Options forwarded to Astro `Image` when `zoomable`.' },
    },
    args: {
        src: SRC,
        alt: 'Rifter, the alliance frigate',
        size: 64,
        narrow: false,
        mask: false,
        zoomable: false,
        thumbnail: false,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Rifter, the alliance frigate' })
        await expect(img).toHaveAttribute('src', SRC)
        await expect(img).toHaveAttribute('width', '64')
        await expect(img).toHaveAttribute('height', '64')
        await expect(img).toHaveAttribute('loading', 'lazy')
        await expect(img.closest('picture')).toHaveClass('animated')
    },
}

export const Large = {
    args: { size: 256, alt: 'Rifter render' },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Rifter render' })
        await expect(img).toHaveAttribute('width', '256')
        await expect(img).toHaveAttribute('height', '256')
    },
}

export const Narrow = {
    args: { size: 256, narrow: true, alt: 'Stabber render', src: 'https://images.evetech.net/types/622/render?size=512' },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Stabber render' })
        await expect(img).toHaveAttribute('width', '256')
        await expect(img).toHaveAttribute('height', '412')
    },
}

export const Masked = {
    args: { size: 256, mask: true, alt: 'Faded Rifter render' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('img')).toHaveClass('mask')
    },
}

export const Thumbnail = {
    args: { size: 128, thumbnail: true, alt: 'Doctrine thumbnail' },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img).toHaveClass('thumbnail-fill')
        await expect(img.closest('picture')).toHaveClass('fixed-thumbnail')
    },
}

export const Placeholder = {
    args: { size: 64, src: 'https://images.evetech.net/types/0/icon?size=64', placeholder: 'https://images.evetech.net/types/587/icon?size=64', alt: 'Fallback icon' },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img.getAttribute('onerror')).toContain('this.src=\'https://images.evetech.net/types/587/icon?size=64\'')
    },
}

export const Decorative = {
    args: { alt: '' },
    play: async ({ canvasElement }: Ctx) => {
        const img = canvasElement.querySelector('img') as HTMLElement
        await expect(img).toBeInTheDocument()
        await expect(img).not.toHaveAttribute('alt')
    },
}

export const Zoomable = {
    args: { zoomable: true, size: 128, alt: 'Zoomable Rifter render' },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Zoomable Rifter render' })
        await expect(img.closest('figure')).toBeInTheDocument()
        await expect(img).toHaveAttribute('loading', 'lazy')
    },
}

export const WithQuantity = {
    args: { quantity: 12, size: 64 },
    play: async ({ canvasElement }: Ctx) => {
        const badge = canvasElement.querySelector('.quantity-badge') as HTMLElement
        await expect(badge).toHaveTextContent('12')
        await expect(badge.closest('picture')).not.toBeNull()
    },
}

export const NoBadgeWithoutQuantity = {
    args: { quantity: 0 },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('.quantity-badge')).toBeNull()
    },
}

export const LinkTarget = {
    name: 'Wrapped in a link target',
    args: { target: { tag: 'a', attrs: { href: '/alliance/corporations/1/' } }, brighten: true },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link).toHaveAttribute('href', '/alliance/corporations/1/')
        await expect(link.querySelector('img')).not.toBeNull()
        await expect(canvasElement.querySelector('picture')).toHaveClass('brighten')
    },
}
