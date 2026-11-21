import { expect, within, userEvent, waitFor } from 'storybook/test'
import FilterChip from '@components/blocks/FilterChip.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Navigation/FilterChip',
    component: FilterChip,
    parameters: {
        docs: {
            description: {
                component: [
                    'A pill-shaped toggle for filtering a list. As a `<button>` (client-side filter) it reports state with `aria-pressed`; with `href` it is a link to a filtered view and marks the current one with `aria-current="page"`.',
                    'For an Alpine filter, bind `x-bind:class` (`is-active`), `x-bind:aria-pressed` and `x-on:click` yourself; `active` is only the server-rendered starting state. Put chips in a `ChipGroup` so they scroll sideways with an edge fade instead of overflowing.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        active: { control: 'boolean', description: 'Server-rendered selected state: `is-active` class plus `aria-pressed` / `aria-current`.' },
        href: { control: 'text', description: 'Render a link to a filtered view instead of a toggle button.' },
        class: { control: 'text', description: 'Extra classes.' },
    },
    args: {
        active: false,
        slots: { default: 'Frigates' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: 'Frigates' })
        await expect(chip).toHaveClass('filter-chip')
        await expect(chip).not.toHaveClass('is-active')
        await expect(chip).toHaveAttribute('aria-pressed', 'false')
        await expect(chip).toHaveAttribute('type', 'button')
    },
}

export const Active = {
    args: { active: true },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: 'Frigates' })
        await expect(chip).toHaveClass('is-active')
        await expect(chip).toHaveAttribute('aria-pressed', 'true')
    },
}

export const AlpineToggle = {
    name: 'Alpine toggle',
    // Alpine state lives on the chip itself here; a real filter shares it on a parent (see ChipGroup).
    args: {
        'x-data': '{ on: false }',
        'x-on:click': 'on = !on',
        'x-bind:aria-pressed': "on ? 'true' : 'false'",
        slots: { default: 'Hide off-doctrine' },
    },
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: 'Hide off-doctrine' })
        await waitFor(() => expect(chip).toHaveAttribute('aria-pressed', 'false'))
        await userEvent.click(chip)
        await waitFor(() => expect(chip).toHaveAttribute('aria-pressed', 'true'))
        await userEvent.click(chip)
        await waitFor(() => expect(chip).toHaveAttribute('aria-pressed', 'false'))
    },
}

export const LinkChip = {
    name: 'Link to a filtered view',
    args: { href: '/fleets/history/?type=strategic', slots: { default: 'Strategic' } },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('link', { name: 'Strategic' })
        await expect(chip).toHaveAttribute('href', '/fleets/history/?type=strategic')
        await expect(chip).not.toHaveAttribute('aria-current')
        await expect(within(canvasElement).queryByRole('button')).toBeNull()
    },
}

export const ActiveLinkChip = {
    name: 'Current link chip',
    args: { href: '/fleets/history/?type=strategic', active: true, slots: { default: 'Strategic' } },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('link', { name: 'Strategic' })
        await expect(chip).toHaveAttribute('aria-current', 'page')
        await expect(chip).toHaveClass('is-active')
    },
}

export const Passthrough = {
    name: 'Attributes pass through',
    args: { 'data-filter': 'frigate', class: 'my-chip' },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button')
        await expect(chip).toHaveAttribute('data-filter', 'frigate')
        await expect(chip).toHaveClass('filter-chip', 'my-chip')
    },
}
