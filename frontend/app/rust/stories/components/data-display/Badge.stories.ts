import { expect, within } from 'storybook/test'
import Badge from '@components/blocks/Badge.astro'
import { EVE, select_control } from '../../_controls'

type Play = { canvasElement: HTMLElement }

const portrait = (size: number) => `https://images.evetech.net/characters/${EVE.character_id}/portrait?size=${Math.max(size, 32)}`
const corp_logo = (size: number) => `https://images.evetech.net/corporations/${EVE.corporation_id}/logo?size=${Math.max(size, 32)}`

export default {
    title: 'Components/Data display/Badge',
    component: Badge,
    parameters: {
        docs: {
            description: {
                component: [
                    'A picture beside a title and optional subtitle: how pilots, corporations and alliances are listed. It is a `FixedFluid` row, so the picture is exactly `size` pixels wide and the text fills the rest.',
                    'Pass `image` for the usual square picture, or fill the `picture` slot to supply your own (an icon, a stack of logos). The `title` slot sits right after the title text (flags, tags), and the default slot replaces the subtitle line when you need more than one string.',
                    'Not related to `NotificationBadge`, the small count bubble. For a corporation or alliance, prefer `CorporationBadge` / `AllianceBadge`, which already know the logo URLs. `size` also picks the gap: 16 or less is tight, under 64 medium, 64 and up wide.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        title: { control: 'text', description: 'Main line, in highlight colour unless `highlight` is off.' },
        subtitle: { control: 'text', description: 'Small yellow line under the title. Ignored when the default slot is filled.' },
        image: { control: 'text', description: 'URL of the square picture.' },
        size: { control: { type: 'number', min: 16, max: 128, step: 8 }, description: 'Picture width and height in pixels.' },
        border: { control: 'boolean', description: 'Frame the picture with the border colour.' },
        highlight: { control: 'boolean', description: 'Colour the title with `--highlight`.' },
        title_el: select_control(['span', 'h2', 'h3', 'h4', 'p'] as const, 'Element for the title. Anything but `span` also adds a gap between title and subtitle.'),
    },
    args: {
        title: EVE.character_name,
        subtitle: EVE.corporation_name,
        image: portrait(64),
        size: 64,
        border: false,
        highlight: true,
        title_el: 'span',
    },
}

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(EVE.character_name)).toHaveClass('text-highlight')
        await expect(canvas.getByText(EVE.corporation_name).tagName).toBe('SMALL')
        const img = canvasElement.querySelector('img') as HTMLImageElement
        await expect(img).toHaveAttribute('width', '64')
        await expect(img).toHaveAttribute('height', '64')
        await expect(img).toHaveAttribute('loading', 'lazy')
    },
}

export const Small = {
    args: { size: 32, image: portrait(32), title: 'FC Bear', subtitle: 'Fleet commander' },
    play: async ({ canvasElement }: Play) => {
        const img = canvasElement.querySelector('img') as HTMLImageElement
        await expect(img).toHaveAttribute('width', '32')
        await expect(within(canvasElement).getByText('Fleet commander')).toBeVisible()
    },
}

export const Tiny = {
    args: { size: 16, image: corp_logo(16), title: EVE.corporation_ticker, subtitle: undefined },
    play: async ({ canvasElement }: Play) => {
        await expect(canvasElement.querySelector('img')).toHaveAttribute('width', '16')
        await expect(canvasElement.querySelector('small')).toBeNull()
    },
}

export const Large = {
    args: { size: 128, image: corp_logo(128), title: EVE.corporation_name, subtitle: `${EVE.corporation_ticker} · 412 members` },
    play: async ({ canvasElement }: Play) => {
        await expect(canvasElement.querySelector('img')).toHaveAttribute('width', '128')
        await expect(within(canvasElement).getByText(/412 members/)).toBeVisible()
    },
}

export const Bordered = {
    args: { border: true },
    play: async ({ canvasElement }: Play) => {
        await expect(canvasElement.querySelector('picture')).toHaveClass('border')
    },
}

export const MutedTitle = {
    name: 'Without highlight',
    args: { highlight: false },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText(EVE.character_name)).not.toHaveClass('text-highlight')
    },
}

export const HeadingTitle = {
    args: { title_el: 'h3', title: EVE.alliance_name, subtitle: EVE.alliance_ticker },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByRole('heading', { level: 3, name: new RegExp(EVE.alliance_name) })).toBeVisible()
    },
}

export const NoImage = {
    args: { image: undefined, title: 'Unknown pilot', subtitle: 'Picture not loaded yet' },
    play: async ({ canvasElement }: Play) => {
        await expect(canvasElement.querySelector('picture')).not.toBeNull()
        await expect(canvasElement.querySelector('img')).toBeNull()
    },
}

export const SlotContent = {
    name: 'Title and subtitle slots',
    args: {
        subtitle: undefined,
        slots: {
            title: '<span class="text-muted">(FC)</span>',
            default: '<small>Last seen in <strong>Amamake</strong></small><small>Flying a Rifter</small>',
        },
    },
    play: async ({ canvasElement }: Play) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('(FC)')).toBeVisible()
        await expect(canvas.getByText('Amamake')).toBeVisible()
        await expect(canvas.getByText('Flying a Rifter')).toBeVisible()
    },
}

export const ImageHasAlt = {
    name: 'Image uses the title as alt text',
    play: async ({ canvasElement }: Play) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('img', { name: EVE.character_name })).toHaveAttribute('alt', EVE.character_name)
    },
}
