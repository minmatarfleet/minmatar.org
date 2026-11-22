import { expect, within } from 'storybook/test'
import CorporationPicture from '@components/blocks/CorporationPicture.astro'
import { BADGE_COLORS, select_control, EVE } from '../_controls'

const SIZES = [16, 24, 32, 64, 128, 256, 512, 1024] as const
const QUALITIES = [32, 64, 128, 256, 512, 1024] as const
const logo = (size: number) => `https://images.evetech.net/corporations/${EVE.corporation_id}/logo?size=${size}`

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'EVE/CorporationPicture',
    component: CorporationPicture,
    parameters: {
        docs: {
            description: {
                component: [
                    'A corporation logo from the EVE image server. The logo is a real link to the corporation detail page (`/alliance/corporations/<id>/`), so it can be opened with the keyboard and in a new tab; id 0 is not linked.',
                    'It is a bare image: for a logo with a name beside it use `CorporationBadge`. `size` is the rendered width and height; `icon_quality` the image-server size requested. `x_corporation_id` / `x_corporation_name` accept Alpine expressions for reactive pickers; leave them `false` otherwise.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        corporation_id: { control: 'number', description: 'EVE corporation id.' },
        corporation_name: { control: 'text', description: 'Used in the alt text. Falls back to "Unknown corporation".' },
        x_corporation_id: { control: 'text', description: 'Alpine expression that overrides `corporation_id` at runtime. `false` disables it.' },
        x_corporation_name: { control: 'text', description: 'Alpine expression that overrides the alt name at runtime. `false` disables it.' },
        size: select_control(SIZES, 'Rendered width and height in px.'),
        icon_quality: select_control(QUALITIES, 'Image-server size requested (the `?size=` parameter).'),
        quantity: { control: 'number', description: 'Shows a corner count badge.' },
        tag_color: select_control(BADGE_COLORS, 'Colour of the corner count badge.'),
    },
    args: {
        corporation_id: EVE.corporation_id,
        corporation_name: EVE.corporation_name,
        x_corporation_id: false,
        x_corporation_name: false,
        size: 64,
        icon_quality: 64,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: `Profile picture of ${EVE.corporation_name}` })
        await expect(img).toHaveAttribute('src', logo(64))
        await expect(img).toHaveAttribute('width', '64')
        await expect(img).toHaveAttribute('height', '64')
        await expect(img).toHaveAttribute('loading', 'lazy')
        // The logo is a real link to the corporation page, not a click handler on the image.
        const link = within(canvasElement).getByRole('link', { name: `Profile picture of ${EVE.corporation_name}` })
        await expect(link).toHaveAttribute('href', `/alliance/corporations/${EVE.corporation_id}/`)
        await expect(link).toContainElement(img)
        await expect(img).not.toHaveAttribute('x-on:click.stop')
    },
}

export const Large = {
    args: { size: 128, icon_quality: 128 },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img).toHaveAttribute('width', '128')
        await expect(img).toHaveAttribute('src', logo(128))
    },
}

export const Small = {
    args: { size: 24, icon_quality: 32 },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img).toHaveAttribute('height', '24')
        await expect(img).toHaveAttribute('src', logo(32))
    },
}

export const WithQuantity = {
    args: { quantity: 12, tag_color: 'green' },
    play: async ({ canvasElement }: Ctx) => {
        const badge = within(canvasElement).getByText('12')
        await expect(badge.className).toContain('quantity-badge')
    },
}

export const DifferentCorporation = {
    args: { corporation_id: 1000115, corporation_name: 'University of Caille' },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Profile picture of University of Caille' })
        await expect(img).toHaveAttribute('src', 'https://images.evetech.net/corporations/1000115/logo?size=64')
    },
}

export const UnknownCorporation = {
    args: { corporation_id: 0, corporation_name: undefined },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('img', { name: 'Profile picture of Unknown corporation' })).toBeVisible()
        // Corporation 0 has no page: nothing to link to.
        await expect(within(canvasElement).queryByRole('link')).toBeNull()
    },
}

export const ZeroQuantity = {
    name: 'Zero quantity shows no badge',
    args: { quantity: 0 },
    play: async ({ canvasElement }: Ctx) => {
        // `{quantity && ...}` used to print a literal 0 beside the logo.
        await expect(canvasElement.querySelector('.quantity-badge')).toBeNull()
        await expect(canvasElement.querySelector('picture')?.textContent?.trim()).toBe('')
    },
}

export const ReactiveLink = {
    name: 'Reactive id binds the link',
    args: { x_corporation_id: '1000115' },
    play: async ({ canvasElement }: Ctx) => {
        const link = canvasElement.querySelector('a.picture-target') as HTMLElement
        await expect(link.getAttribute('x-bind:href')).toContain('/alliance/corporations/')
        // Alpine fills the href from the expression.
        await expect(link).toHaveAttribute('href', '/alliance/corporations/1000115/')
    },
}
