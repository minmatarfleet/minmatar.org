import { expect, within } from 'storybook/test'
import PilotBadge from '@components/blocks/PilotBadge.astro'
import { select_control, EVE } from '../_controls'

const SIZES = [16, 24, 32, 64, 128, 256, 512, 1024] as const
const QUALITIES = [32, 64, 128, 256, 512, 1024] as const
const portrait = (size: number) => `https://images.evetech.net/characters/${EVE.character_id}/portrait?size=${size}`

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'EVE/PilotBadge',
    component: PilotBadge,
    parameters: {
        docs: {
            description: {
                component: [
                    'A pilot portrait with the name beside it, optionally with the pilot\'s corporation underneath. The standard way to list pilots in rosters, fleet members and requests; clicking the name or portrait opens the character modal unless `inert`.',
                    'The default slot renders under the name (and the corporation); the `title` slot sits inline after the name (tags, badges). `size` scales the portrait, the gap and the layout. Character id 0 renders as "[ Unknown character ]" and is not clickable. Extra attributes pass through to the wrapper.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        character_id: { control: 'number', description: 'EVE character id.' },
        character_name: { control: 'text', description: 'Pilot name shown beside the portrait.' },
        corporation: { control: 'object', description: '`{ id, name }` to show the corporation logo and name below; `false` hides it.' },
        size: select_control(SIZES, 'Portrait width in px; the gap tightens at 16 and below.'),
        icon_quality: select_control(QUALITIES, 'Image-server size requested for the portrait.'),
        inert: { control: 'boolean', description: 'No pointer events: the badge sits inside another link.' },
        heading: { control: 'boolean', description: 'Render the name as an `<h3>` instead of a `<span>`.' },
        centered: { control: 'boolean', description: 'Vertically center the portrait.' },
    },
    args: {
        character_id: EVE.character_id,
        character_name: EVE.character_name,
        corporation: false,
        size: 64,
        icon_quality: 64,
        inert: false,
        heading: false,
        centered: false,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(EVE.character_name)).toBeVisible()
        const img = canvas.getByRole('img', { name: `Profile picture of ${EVE.character_name}` })
        await expect(img).toHaveAttribute('src', portrait(64))
        await expect(img).toHaveAttribute('width', '64')
        await expect(canvas.getByText(EVE.character_name).getAttribute('x-on:click.stop.prevent')).toBe('show_character_modal()')
        await expect(canvasElement.querySelector('.pilot-item')).not.toHaveClass('inert')
    },
}

export const WithCorporation = {
    args: { corporation: { id: EVE.corporation_id, name: EVE.corporation_name } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(EVE.corporation_name)).toBeVisible()
        const logo = canvas.getByRole('img', { name: `Profile picture of ${EVE.corporation_name}` })
        await expect(logo).toHaveAttribute('src', `https://images.evetech.net/corporations/${EVE.corporation_id}/logo?size=32`)
    },
}

export const WithTitleAndSlot = {
    args: {
        corporation: { id: EVE.corporation_id, name: EVE.corporation_name },
        slots: {
            title: '<span class="tag">FC</span>',
            default: '<small>Last fleet: Stabber fleet, 2 days ago</small>',
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('FC')).toBeVisible()
        await expect(canvas.getByText('Last fleet: Stabber fleet, 2 days ago')).toBeVisible()
    },
}

export const Heading = {
    args: { heading: true, size: 128, icon_quality: 128 },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('heading', { level: 3, name: EVE.character_name })).toBeVisible()
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
        await expect(canvasElement.querySelector('.pilot-item')).toHaveClass('inert')
    },
}

export const UnknownPilot = {
    args: { character_id: 0, character_name: 'Ghost' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('[ Unknown character ]')).toBeVisible()
        await expect(within(canvasElement).queryByText('Ghost')).toBeNull()
    },
}
