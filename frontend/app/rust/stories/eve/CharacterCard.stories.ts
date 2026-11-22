import { expect, within } from 'storybook/test'
import CharacterCard from '@components/blocks/CharacterCard.astro'
import Button from '@components/blocks/Button.astro'
import { radio_control, EVE } from '../_controls'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'EVE/CharacterCard',
    component: CharacterCard,
    parameters: {
        docs: {
            description: {
                component: [
                    'A tall pilot portrait card (the picture `Card` with a masked 512px portrait cover). Use it for volunteer pickers and candidate lists where the face matters; use `PilotBadge` for dense rows.',
                    'The default slot overlays the bottom of the portrait (name, role); `header`, `actions` and `visible-actions` slots map to the `Card` slots (`actions` appear on hover). `inert` stops the portrait opening the character modal, which matters when the whole card is already a button. Extra attributes pass to `Card`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        character_id: { control: 'number', description: 'EVE character id.' },
        character_name: { control: 'text', description: 'Alt text for the portrait.' },
        inert: { control: 'boolean', description: 'Portrait does not open the character modal.' },
        size: radio_control(['sm', 'lg'] as const, '`sm` crops the portrait to 320px tall; `lg` keeps the full height.'),
        narrow: { control: 'boolean', description: 'Use the tall (narrow) crop for the portrait.' },
    },
    args: {
        character_id: EVE.character_id,
        character_name: EVE.character_name,
        inert: false,
        size: 'lg',
        narrow: true,
        slots: { default: `<strong>${EVE.character_name}</strong><br><small>${EVE.corporation_name}</small>` },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const img = canvas.getByRole('img', { name: `Profile picture of ${EVE.character_name}` })
        await expect(img).toHaveAttribute('src', `https://images.evetech.net/characters/${EVE.character_id}/portrait?size=512`)
        await expect(img).toHaveAttribute('width', '256')
        await expect(img).toHaveAttribute('height', '412')
        await expect(img).toHaveClass('mask')
        await expect(canvas.getByText(EVE.corporation_name)).toBeVisible()
        await expect(canvas.getByRole('button', { name: `Profile picture of ${EVE.character_name}` }).getAttribute('x-on:click.stop.prevent')).toBe('show_character_modal()')
    },
}

export const Small = {
    args: { size: 'sm' },
    play: async ({ canvasElement }: Ctx) => {
        // `sm` passes height 320 but `narrow` still decides whether it applies.
        const img = within(canvasElement).getByRole('img')
        await expect(img).toHaveAttribute('height', '320')
    },
}

export const Inert = {
    args: { inert: true },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img')
        await expect(img).not.toHaveAttribute('x-on:click.stop.prevent')
        await expect(img.closest('picture')).toHaveClass('animated')
    },
}

export const WithActions = {
    args: {
        inert: true,
        slots: {
            default: `<strong>${EVE.character_name}</strong>`,
            actions: [
                { component: Button, props: { size: 'sm' }, slots: { default: 'Invite to fleet' } },
            ],
            'visible-actions': [
                { component: Button, props: { size: 'sm', color: 'transparent' }, slots: { default: 'View profile' } },
            ],
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: 'Invite to fleet' })).toBeInTheDocument()
        await expect(canvas.getByRole('button', { name: 'View profile' })).toBeVisible()
    },
}

export const WithHeader = {
    args: { slots: { header: '<span class="tag">Fleet commander</span>', default: `<strong>${EVE.character_name}</strong>` } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('Fleet commander')).toBeInTheDocument()
    },
}

export const OtherPilot = {
    args: { character_id: 91316135, character_name: 'Aria Talvanen', slots: { default: '<strong>Aria Talvanen</strong>' } },
    play: async ({ canvasElement }: Ctx) => {
        const img = within(canvasElement).getByRole('img', { name: 'Profile picture of Aria Talvanen' })
        await expect(img.getAttribute('src')).toContain('/characters/91316135/portrait')
    },
}
