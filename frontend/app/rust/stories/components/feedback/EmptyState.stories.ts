import { expect, within } from 'storybook/test'
import EmptyState from '@components/blocks/EmptyState.astro'
import Button from '@components/blocks/Button.astro'

export default {
    title: 'Components/Feedback/EmptyState',
    component: EmptyState,
    parameters: {
        docs: {
            description: {
                component: [
                    'The "nothing here" message for a list, table or panel with no rows. Plain, it is one muted line; with a `hint`, `prominent`, or an `action` slot it becomes a highlighted title with room for guidance and a button.',
                    'Styles are global (`_empty-state.scss`), so it works inside htmx partials. Use `ErrorRefetch` for failed fetches, never EmptyState, and do not add new `__empty` styles.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        title: { control: 'text', description: 'The message. Comes from `t(...)` on the site.' },
        hint: { control: 'text', description: 'Small guidance under the title; switches to the prominent layout.' },
        prominent: { control: 'boolean', description: 'Prominent layout without needing a hint.' },
        class: { control: 'text', description: 'Extra classes, merged after the component classes.' },
    },
    args: {
        title: 'No fleets are scheduled right now.',
        prominent: false,
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const message = within(canvasElement).getByText('No fleets are scheduled right now.')
        await expect(message.tagName).toBe('P')
        await expect(message).toHaveClass('empty-state')
        await expect(message).not.toHaveClass('empty-state--prominent')
    },
}

export const Prominent = {
    args: { prominent: true, title: 'No doctrines yet' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const title = within(canvasElement).getByText('No doctrines yet')
        await expect(title).toHaveClass('empty-state__title')
        await expect(title.parentElement).toHaveClass('empty-state--prominent')
        await expect(canvasElement.querySelector('.empty-state__hint')).toBeNull()
    },
}

export const WithHint = {
    args: {
        title: 'No SRP requests',
        hint: 'Requests appear here after you lose a ship in a fleet that is covered by SRP.',
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No SRP requests')).toHaveClass('empty-state__title')
        const hint = canvas.getByText(/Requests appear here/)
        await expect(hint.tagName).toBe('SMALL')
        await expect(hint).toHaveClass('empty-state__hint')
    },
}

export const WithAction = {
    args: {
        title: 'You have not joined any fleet',
        hint: 'Upcoming fleets are listed on the schedule.',
        slots: {
            action: { component: Button, props: { href: '/fleets/upcoming/', size: 'sm' }, slots: { default: 'See upcoming fleets' } },
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const link = canvas.getByRole('link', { name: 'See upcoming fleets' })
        await expect(link).toHaveAttribute('href', '/fleets/upcoming/')
        await expect(link.closest('.empty-state--prominent')).not.toBeNull()
    },
}

export const CustomClassAndAttributes = {
    name: 'Custom class and attributes',
    args: {
        title: 'No corporation members match this filter.',
        class: 'text-center',
        role: 'status',
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const status = within(canvasElement).getByRole('status')
        await expect(status).toHaveClass('empty-state', 'text-center')
    },
}

export const InlineSlotText = {
    name: 'Text through the default slot',
    args: { title: 'No kills in the last', slots: { default: ' 30 days' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('No kills in the last 30 days')).toBeVisible()
    },
}
