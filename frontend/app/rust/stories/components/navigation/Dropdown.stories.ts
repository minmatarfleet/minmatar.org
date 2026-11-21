import { expect, screen, userEvent, waitFor, within } from 'storybook/test'
import Button from '@components/blocks/Button.astro'
import Dropdown from '@components/blocks/Dropdown.astro'
import { BUTTON_COLORS, BUTTON_SIZES, radio_control, select_control } from '../../_controls'

const panel_items = `
    <ul class="list-none">
        <li><a href="/fleets/upcoming/">Upcoming fleets</a></li>
        <li><a href="/fleets/history/">Fleet history</a></li>
        <li><a href="/my-srp/">My SRP</a></li>
    </ul>`

export default {
    title: 'Components/Navigation/Dropdown',
    component: Dropdown,
    parameters: {
        docs: {
            description: {
                component: [
                    'The generic popover: a trigger (`button` slot) that toggles a panel (default slot) anchored under it. Use `ActionMenu` for a list of actions; reach for `Dropdown` directly when the panel holds arbitrary content such as filters or a small form.',
                    'The panel is teleported to `<body>` with `x-teleport` and positioned with `x-anchor`, so it is not inside the component\'s DOM and is not clipped by `overflow: hidden` parents. Escape and a mousedown outside close it; the trigger carries `aria-haspopup` and `aria-expanded`.',
                    'The root also gets the `is-open` class while open. Htmx content inside the panel is processed when it opens.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        variant: radio_control(['default', 'button'] as const, '`default` is a text trigger with a chevron; `button` is the solid button trigger.'),
        color: select_control(BUTTON_COLORS, 'Trigger button color (variant `button`).'),
        size: radio_control(BUTTON_SIZES, 'Trigger button size (variant `button`).'),
        trigger_label: { control: 'text', description: 'Accessible name for the trigger when its visible text alone is ambiguous (one menu per row).' },
    },
    args: {
        variant: 'default',
        color: 'fleet-red',
        size: 'sm',
        slots: { button: 'Fleets', default: panel_items },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Fleets' })
        await expect(trigger).toHaveAttribute('aria-haspopup', 'true')
        await expect(trigger).toHaveAttribute('aria-expanded', 'false')
        await waitFor(() => expect(screen.getByText('Fleet history')).not.toBeVisible())

        await userEvent.click(trigger)
        await expect(trigger).toHaveAttribute('aria-expanded', 'true')
        await waitFor(() => expect(screen.getByRole('link', { name: 'Fleet history' })).toBeVisible())
        await expect(canvasElement.firstElementChild).toHaveClass('is-open')

        await userEvent.click(trigger)
        await expect(trigger).toHaveAttribute('aria-expanded', 'false')
        await expect(canvasElement.firstElementChild).not.toHaveClass('is-open')
    },
}

export const ButtonVariant = {
    args: { variant: 'button', color: 'alliance-blue', size: 'lg', slots: { button: 'Doctrines', default: panel_items } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Doctrines' })
        await expect(trigger).toHaveAttribute('data-appearance', 'button')
        await expect(trigger).toHaveAttribute('data-size', 'lg')
        await expect(trigger.getAttribute('style')).toContain('var(--alliance-blue)')
        await userEvent.click(trigger)
        await expect(trigger).toHaveAttribute('aria-expanded', 'true')
        await expect((await screen.findByRole('link', { name: 'My SRP' })).closest('.dropdown-panel')).toHaveClass('button-dropdown-panel')
    },
}

export const EscapeCloses = {
    name: 'Escape closes the panel',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Fleets' })
        await userEvent.click(trigger)
        await expect(trigger).toHaveAttribute('aria-expanded', 'true')
        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(trigger).toHaveAttribute('aria-expanded', 'false'))
        await waitFor(() => expect(screen.getByText('Fleet history')).not.toBeVisible())
    },
}

export const OutsideClickCloses = {
    // Alpine's `.outside` ignores elements with no layout size, which happy-dom never reports.
    tags: ['browser'],
    name: 'Outside click closes the panel',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Fleets' })
        await userEvent.click(trigger)
        await expect(trigger).toHaveAttribute('aria-expanded', 'true')
        // The open panel is fixed over the canvas, so a click on the canvas's
        // centre can land on the panel itself. Press on the page instead.
        // Alpine's .outside ignores an element with no size, so wait until the
        // teleported panel is laid out before pressing outside it.
        await waitFor(() => {
            const panel = document.querySelector<HTMLElement>('.dropdown-panel')
            expect(panel && panel.offsetHeight > 0).toBe(true)
        })
        await userEvent.pointer({ keys: '[MouseLeft>]', target: document.body })
        await waitFor(() => expect(trigger).toHaveAttribute('aria-expanded', 'false'))
    },
}

export const LabelledTrigger = {
    args: { trigger_label: 'Fleet links for FL33T', slots: { button: 'Links', default: panel_items } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Fleet links for FL33T' })
        await expect(trigger).toHaveTextContent('Links')
    },
}

export const FilterPanel = {
    name: 'Panel with controls',
    args: {
        variant: 'button',
        color: 'transparent',
        slots: {
            button: 'Filter ships',
            default: [
                { component: Button, props: { size: 'sm', color: 'alliance-blue' }, slots: { default: 'Rifter' } },
                { component: Button, props: { size: 'sm', color: 'transparent' }, slots: { default: 'Stabber' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Filter ships' })
        await userEvent.click(trigger)
        const rifter = await screen.findByRole('button', { name: 'Rifter' })
        await waitFor(() => expect(rifter).toBeVisible())
        await expect(screen.getByRole('button', { name: 'Stabber' })).toBeVisible()
        // Interacting inside the panel keeps it open.
        await userEvent.click(rifter)
        await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    },
}
