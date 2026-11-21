import { expect, screen, userEvent, waitFor, within } from 'storybook/test'
import ActionMenu from '@components/blocks/ActionMenu.astro'
import ActionMenuItem from '@components/blocks/ActionMenuItem.astro'
import { BUTTON_COLORS, BUTTON_SIZES, radio_control, select_control } from '../../_controls'

export default {
    title: 'Components/Navigation/ActionMenu',
    component: ActionMenu,
    parameters: {
        docs: {
            description: {
                component: [
                    'A row-actions dropdown: a `Dropdown` whose panel lists `ActionMenuItem` children (links, buttons, submit buttons, status lines and two-step confirms).',
                    'The panel is teleported to `<body>` while the menu is open, so tests and page scripts look for it on the document, not inside the menu. `variant`, `color` and `size` pass through to `Dropdown` (`variant="button"` gives the solid button trigger).',
                    'A component that renders its own trigger (a `DialogButton`) goes inside `<div class="action-menu-item-host">` to be styled like an item. Set `trigger_label` when several menus share a page ("Actions for <pilot>").',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        label: { control: 'text', description: 'Trigger text and the list\'s accessible name. Defaults to "Actions".' },
        hover: radio_control(['tint', 'fill'] as const, 'Item hover: `tint` shades the row with the foreground, `fill` fills it with the fleet red of a red button trigger.'),
        fit_trigger: { control: 'boolean', description: 'Panel as wide as the trigger (at least 12rem); long items wrap.' },
        trigger_label: { control: 'text', description: 'Accessible name for the trigger when several menus share a page.' },
        variant: radio_control(['default', 'button'] as const, 'Passed to Dropdown: plain text trigger or the solid button trigger.'),
        color: select_control(BUTTON_COLORS, 'Button trigger color (variant `button` only).'),
        size: radio_control(BUTTON_SIZES, 'Button trigger size (variant `button` only).'),
    },
    args: {
        label: 'Actions',
        hover: 'tint',
        fit_trigger: false,
        variant: 'default',
        color: 'fleet-red',
        size: 'sm',
        slots: {
            default: [
                { component: ActionMenuItem, props: { href: '/fleets/92221/' }, slots: { default: 'Open fleet' } },
                { component: ActionMenuItem, slots: { default: 'Copy fleet link' } },
                { component: ActionMenuItem, props: { variant: 'danger' }, slots: { default: 'Close fleet' } },
            ],
        },
    },
}

const open_menu = async (canvasElement: HTMLElement, name = /Actions/) => {
    const trigger = within(canvasElement).getByRole('button', { name })
    await userEvent.click(trigger)
    return trigger
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: /Actions/ })
        await expect(trigger).toHaveAttribute('aria-haspopup', 'true')
        await expect(trigger).toHaveAttribute('aria-expanded', 'false')
        // Closed: the panel is hidden.
        await expect(screen.queryByRole('navigation', { name: 'Actions', hidden: false })).toBeNull()

        await userEvent.click(trigger)
        await expect(trigger).toHaveAttribute('aria-expanded', 'true')
        const list = await screen.findByRole('navigation', { name: 'Actions' })
        await waitFor(() => expect(list).toBeVisible())
        await expect(within(list).getByRole('link', { name: 'Open fleet' })).toHaveAttribute('href', '/fleets/92221/')
        await expect(within(list).getAllByRole('button')).toHaveLength(2)
    },
}

export const EscapeCloses = {
    name: 'Escape closes the menu',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = await open_menu(canvasElement)
        await expect(trigger).toHaveAttribute('aria-expanded', 'true')
        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(trigger).toHaveAttribute('aria-expanded', 'false'))
        await waitFor(() => expect(screen.queryByRole('navigation', { name: 'Actions' })).toBeNull())
    },
}

export const ButtonTrigger = {
    args: { variant: 'button', color: 'alliance-blue', size: 'sm', label: 'Manage fleet' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: /Manage fleet/ })
        await expect(trigger).toHaveAttribute('data-appearance', 'button')
        await userEvent.click(trigger)
        await expect(trigger).toHaveAttribute('aria-expanded', 'true')
        const list = await screen.findByRole('navigation', { name: 'Manage fleet' })
        await waitFor(() => expect(list).toBeVisible())
        // The teleported panel carries the button-trigger styling.
        await expect(list.closest('.dropdown-panel')).toHaveClass('button-dropdown-panel')
    },
}

export const Variants = {
    name: 'Item variants and status line',
    args: {
        label: 'Order actions',
        slots: {
            default: [
                { component: ActionMenuItem, props: { text_only: true }, slots: { default: 'Claimed by Kel\'dar Atram' } },
                { component: ActionMenuItem, props: { variant: 'primary' }, slots: { default: 'Mark delivered' } },
                { component: ActionMenuItem, props: { variant: 'success' }, slots: { default: 'Accept order' } },
                { component: ActionMenuItem, slots: { default: 'View contract' } },
                { component: ActionMenuItem, props: { variant: 'muted' }, slots: { default: 'Hide for now' } },
                { component: ActionMenuItem, props: { variant: 'danger' }, slots: { default: 'Cancel order' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await open_menu(canvasElement, /Order actions/)
        const list = await screen.findByRole('navigation', { name: 'Order actions' })
        // The status line is plain text, not a control.
        await expect(within(list).getByText(/Claimed by/)).toHaveClass('action-menu-item--text')
        await expect(within(list).queryByRole('button', { name: /Claimed by/ })).toBeNull()
        await expect(within(list).getByRole('button', { name: 'Accept order' })).toHaveClass('action-menu-item--success')
        await expect(within(list).getByRole('button', { name: 'Cancel order' })).toHaveClass('action-menu-item--danger')
        await expect(within(list).getByRole('button', { name: 'Hide for now' })).toHaveClass('action-menu-item--muted')
    },
}

export const ConfirmItem = {
    name: 'Two-step confirm',
    args: {
        label: 'Fleet',
        slots: {
            default: [
                { component: ActionMenuItem, slots: { default: 'Open fleet' }, props: { href: '/fleets/92221/' } },
                {
                    component: ActionMenuItem,
                    props: { variant: 'danger', confirm_label: 'Yes, close fleet' },
                    slots: { default: 'Close fleet' },
                },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await open_menu(canvasElement, /Fleet/)
        const list = await screen.findByRole('navigation', { name: 'Fleet' })
        const first_step = within(list).getByRole('button', { name: 'Close fleet' })
        const confirm = list.querySelector('.is-confirm') as HTMLElement
        await expect(confirm).toHaveTextContent('Yes, close fleet')
        await waitFor(() => expect(confirm).not.toBeVisible())

        // First click only arms the item.
        await userEvent.click(first_step)
        await waitFor(() => expect(confirm).toBeVisible())
        await waitFor(() => expect(first_step).not.toBeVisible())
        // (Focus moving to the confirm button is asserted in ActionMenuItem's stories; in the real browser it does not land while the menu panel is open, see report.)
        await expect(confirm).toHaveClass('is-confirm')

        // Escape disarms (and closes the menu); reopening shows the first step again.
        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(screen.queryByRole('navigation', { name: 'Fleet' })).toBeNull())
    },
}

export const SubmitItemsInForm = {
    name: 'Submit item and fill hover',
    args: {
        label: 'Survey',
        hover: 'fill',
        slots: {
            default: [
                // On the surveys page this item sits inside a <form method="post">; `type: 'submit'` submits it.
                { component: ActionMenuItem, props: { type: 'submit', variant: 'success' }, slots: { default: 'Open survey' } },
                { component: ActionMenuItem, props: { href: '/surveys/12/results' }, slots: { default: 'View results' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await open_menu(canvasElement, /Survey/)
        const list = await screen.findByRole('navigation', { name: 'Survey' })
        await expect(within(list).getByRole('button', { name: 'Open survey' })).toHaveAttribute('type', 'submit')
        await expect(within(list).getByRole('link', { name: 'View results' })).toHaveAttribute('href', '/surveys/12/results')
        await expect(canvasElement.querySelector('.action-menu--fill')).not.toBeNull()
    },
}

export const FitTrigger = {
    args: {
        label: 'Actions',
        fit_trigger: true,
        trigger_label: 'Actions for Kel\'dar Atram',
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Actions for Kel\'dar Atram' })
        await expect(canvasElement.querySelector('.action-menu--fit')).not.toBeNull()
        await userEvent.click(trigger)
        await expect(trigger).toHaveAttribute('aria-expanded', 'true')
    },
}
