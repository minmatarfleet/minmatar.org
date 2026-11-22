import { expect, within } from 'storybook/test'
import Card from '@components/blocks/Card.astro'
import Button from '@components/blocks/Button.astro'
import Badge from '@components/blocks/Badge.astro'
import { EVE } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

const portrait = (id: number, alt: string) =>
    `<img src="https://images.evetech.net/characters/${id}/portrait?size=256" width="256" height="256" alt="${alt}" class="w-full h-auto" />`

export default {
    title: 'Components/Data display/Card',
    component: Card,
    parameters: {
        docs: {
            description: {
                component: [
                    'A picture card built on `ComponentBlock`: a cover fills the card, the body text sits over its bottom edge, a header badge over the top-left, and `actions` fade in at the top-right on hover or keyboard focus (always shown on touch devices).',
                    'Use `visible-actions` for controls that must always be reachable and `actions` for secondary ones; `actions` show on mouse hover, when focus is inside the card, and always on touch devices. For a plain picture with these same slots use `PictureCard`; for a bordered panel without a cover use `ComponentBlock`.',
                    'Card has no props of its own: everything else (class, `data-*`, Alpine or htmx attributes) passes through to the ComponentBlock. The card is capped at `60vh` tall and clips overflow.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        class: { control: 'text', description: 'Extra classes for the card root (merged with `card card-animated`).' },
        slots: { control: 'object', description: 'Named slots: `cover`, default (body), `header`, `actions`, `visible-actions`.' },
    },
    args: {
        slots: {
            cover: portrait(EVE.character_id, EVE.character_name),
            default: `<strong>${EVE.character_name}</strong>`,
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const card = canvasElement.querySelector('.card') as HTMLElement
        await expect(card).toHaveClass('card-animated')
        await expect(canvas.getByRole('img', { name: EVE.character_name })).toHaveAttribute('src', expect.stringContaining(`/characters/${EVE.character_id}/portrait`))
        await expect(card.querySelector('.card-body')).toHaveTextContent(EVE.character_name)
    },
}

export const WithHeader = {
    args: {
        slots: {
            cover: portrait(EVE.character_id, EVE.character_name),
            header: { component: Badge, props: { color: 'alliance-blue' }, slots: { default: 'FC' } },
            default: `<strong>${EVE.character_name}</strong><br /><small>${EVE.corporation_name}</small>`,
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const header = canvasElement.querySelector('.card-header') as HTMLElement
        await expect(within(header).getByText('FC')).toBeVisible()
        await expect(canvas.getByText(EVE.corporation_name)).toBeVisible()
    },
}

export const HoverActions = {
    name: 'Hover actions',
    args: {
        slots: {
            cover: portrait(EVE.character_id, EVE.character_name),
            default: `<strong>${EVE.character_name}</strong>`,
            actions: [
                { component: Button, props: { size: 'sm', href: '/fleets/92221/' }, slots: { default: 'View fleet' } },
                { component: Button, props: { size: 'sm', color: 'transparent' }, slots: { default: 'Kick' } },
            ],
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const actions = canvasElement.querySelector('.card-actions') as HTMLElement
        await expect(within(actions).getByRole('link', { name: 'View fleet' })).toHaveAttribute('href', '/fleets/92221/')
        await expect(within(actions).getByRole('button', { name: 'Kick' })).toBeInTheDocument()
        // Faded-out actions stay in the accessibility tree: the link and the button.
        await expect(canvas.getAllByRole('button')).toHaveLength(1)
    },
}

export const VisibleActions = {
    name: 'Always-visible actions',
    args: {
        slots: {
            cover: portrait(EVE.character_id, EVE.character_name),
            default: `<strong>${EVE.character_name}</strong>`,
            'visible-actions': { component: Button, props: { size: 'sm', color: 'green' }, slots: { default: 'Join' } },
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const visible = canvasElement.querySelector('.visible-actions') as HTMLElement
        await expect(within(visible).getByRole('button', { name: 'Join' })).toBeVisible()
        await expect(canvasElement.querySelector('.card-actions')?.textContent?.trim()).toBe('')
    },
}

export const AllSlots = {
    name: 'All slots',
    args: {
        class: 'rust-demo-card',
        slots: {
            cover: portrait(EVE.character_id, EVE.character_name),
            header: { component: Badge, props: { color: 'militia-purple' }, slots: { default: EVE.corporation_ticker } },
            default: `<strong>${EVE.character_name}</strong>`,
            actions: { component: Button, props: { size: 'sm', color: 'transparent' }, slots: { default: 'Profile' } },
            'visible-actions': { component: Badge, props: { color: 'green' }, slots: { default: 'Online' } },
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelector('.card')).toHaveClass('rust-demo-card')
        await expect(canvas.getByText(EVE.corporation_ticker)).toBeVisible()
        await expect(canvas.getByText('Online')).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Profile' })).toBeInTheDocument()
    },
}

export const NoCover = {
    name: 'No cover (text only)',
    args: { slots: { default: '<strong>Strategic fleet</strong><br /><small>Form up in Amamake at 19:00 EVE</small>' } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.queryByRole('img')).toBeNull()
        await expect(canvas.getByText('Strategic fleet')).toBeVisible()
    },
}

export const Passthrough = {
    name: 'Attributes pass through',
    args: { 'data-testid': 'pilot-card', 'x-data': '{ open: false }' },
    play: async ({ canvasElement }: Ctx) => {
        const card = within(canvasElement).getByTestId('pilot-card')
        await expect(card).toHaveClass('card')
        await expect(card).toHaveAttribute('x-data', '{ open: false }')
    },
}

export const FocusRevealsActions = {
    name: 'Keyboard focus reveals actions',
    tags: ['browser'],
    args: {
        slots: {
            cover: portrait(EVE.character_id, EVE.character_name),
            default: `<strong>${EVE.character_name}</strong>`,
            actions: { component: Button, props: { size: 'sm', href: '/fleets/92221/' }, slots: { default: 'View fleet' } },
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const actions = canvasElement.querySelector('.card-actions') as HTMLElement
        const link = within(actions).getByRole('link', { name: 'View fleet' })
        // Hover-capable pointers start hidden; touch devices (hover: none) always show them.
        if (window.matchMedia('(hover: hover)').matches) await expect(getComputedStyle(actions).opacity).toBe('0')
        link.focus()
        await expect(getComputedStyle(actions).opacity).toBe('1')
    },
}
