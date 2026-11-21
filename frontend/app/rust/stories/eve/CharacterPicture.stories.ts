import { expect, within } from 'storybook/test'
import CharacterPicture from '@components/blocks/CharacterPicture.astro'
import { BADGE_COLORS, select_control, EVE } from '../_controls'

const SIZES = [16, 24, 32, 64, 128, 256, 512, 1024] as const
const QUALITIES = [32, 64, 128, 256, 512, 1024] as const
const portrait = (size: number) => `https://images.evetech.net/characters/${EVE.character_id}/portrait?size=${size}`

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'EVE/CharacterPicture',
    component: CharacterPicture,
    parameters: {
        docs: {
            description: {
                component: [
                    'A pilot portrait from the EVE image server. Clicking it opens the character modal (`/partials/character_modal_component/`) unless `inert` is set; use `inert` inside links or cards that already own the click.',
                    '`size` is the rendered width; `icon_quality` is the image-server size requested (defaults to 64, so pass 256/512 for large portraits to keep them sharp). `x_character_id` / `x_character_name` take Alpine expressions so the portrait can follow reactive state (the picker in a form); leave them `false` for static pages. Character id 0 renders the unknown-character alt and the click does nothing.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        character_id: { control: 'number', description: 'EVE character id.' },
        character_name: { control: 'text', description: 'Used in the alt text ("Profile picture of ..."). Falls back to "Unknown character".' },
        x_character_id: { control: 'text', description: 'Alpine expression that overrides `character_id` at runtime. `false` disables it.' },
        x_character_name: { control: 'text', description: 'Alpine expression that overrides the alt name at runtime. `false` disables it.' },
        size: select_control(SIZES, 'Rendered width in px.'),
        narrow: { control: 'boolean', description: 'Tall crop: height becomes `height` instead of `size`.' },
        icon_quality: select_control(QUALITIES, 'Image-server size requested (the `?size=` parameter).'),
        tooltip: { control: 'text', description: 'Tippy tooltip text (`data-tippy-content`).' },
        mask: { control: 'boolean', description: 'Fade the bottom out with a gradient mask (cards).' },
        inert: { control: 'boolean', description: 'No click action, no hover brighten (`animated` class).' },
        centered: { control: 'boolean', description: 'Center the picture vertically in a flex parent.' },
        quantity: { control: 'number', description: 'Shows a corner count badge.' },
        tag_color: select_control(BADGE_COLORS, 'Colour of the corner count badge.'),
        height: { control: 'number', description: 'Image height in px when `narrow`.' },
    },
    args: {
        character_id: EVE.character_id,
        character_name: EVE.character_name,
        x_character_id: false,
        x_character_name: false,
        size: 64,
        narrow: false,
        icon_quality: 64,
        mask: false,
        inert: false,
        centered: false,
        height: 412,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: `Profile picture of ${EVE.character_name}` })
        await expect(img).toHaveAttribute('src', portrait(64))
        await expect(img).toHaveAttribute('width', '64')
        await expect(img).toHaveAttribute('height', '64')
        // Clickable: Alpine opens the character modal.
        await expect(img.getAttribute('x-on:click.stop.prevent')).toBe('show_character_modal()')
        await expect(img.getAttribute('x-data')).toContain(`'${EVE.character_id}'`)
        await expect(img.closest('picture')).not.toHaveClass('animated')
    },
}

export const LargePortrait = {
    args: { size: 256, icon_quality: 512 },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img).toHaveAttribute('width', '256')
        await expect(img).toHaveAttribute('src', portrait(512))
    },
}

export const Small = {
    args: { size: 24, icon_quality: 32 },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img).toHaveAttribute('width', '24')
        await expect(img).toHaveAttribute('src', portrait(32))
    },
}

export const Inert = {
    args: { inert: true },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img.closest('picture')).toHaveClass('animated')
        await expect(img).not.toHaveAttribute('x-on:click.stop.prevent')
    },
}

export const WithQuantity = {
    args: { quantity: 3, tag_color: 'alliance-blue' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('3')).toBeVisible()
        await expect(canvas.getByText('3').className).toContain('quantity-badge')
    },
}

export const Masked = {
    args: { size: 256, icon_quality: 512, mask: true, narrow: true, height: 320 },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img).toHaveClass('mask')
        await expect(img).toHaveAttribute('height', '320')
    },
}

export const UnknownCharacter = {
    args: { character_id: 0, character_name: undefined },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Profile picture of Unknown character' })
        await expect(img.getAttribute('src')).toContain('/characters/0/portrait')
    },
}

export const WithTooltip = {
    tags: ['browser'],
    args: { tooltip: 'FC for tonight' },
    play: async ({ canvasElement }: Ctx) => {
        const picture = canvasElement.querySelector('picture') as HTMLElement
        await expect(picture).toHaveAttribute('data-tippy-content', 'FC for tonight')
        await expect(picture).toHaveAttribute('x-init', 'tippy($el, tippy_options)')
    },
}
