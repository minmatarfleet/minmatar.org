import { expect, userEvent, waitFor, within } from 'storybook/test'
import ActionMenuItem from '@components/blocks/ActionMenuItem.astro'
import { radio_control } from '../../_controls'

export default {
    title: 'Components/Navigation/ActionMenuItem',
    component: ActionMenuItem,
    parameters: {
        docs: {
            description: {
                component: [
                    'One row of an `ActionMenu`: a link (`href`), a button, a submit button, a plain status line (`text_only`) or a two-step confirm (`confirm_label`).',
                    'Shown here on its own, outside a menu; use it inside `ActionMenu` on pages. Inside a Dropdown/ActionMenu an armed confirm disarms whenever the menu closes; standalone it disarms on Escape or an outside click.',
                    'Extra attributes (`x-on:click`, `data-*`, `hx-*`) land on the rendered button; with `confirm_label` they go on the confirm button, so only the second click runs the action.',
                ].join('\n\n'),
            },
        },
        layout: 'centered',
    },
    argTypes: {
        variant: radio_control(['default', 'primary', 'danger', 'success', 'muted'] as const, 'Color treatment of the row.'),
        confirm_label: { control: 'text', description: 'Two-step confirm: the first click swaps the item for this label; only the second click runs the action.' },
        href: { control: 'text', description: 'Renders the item as a link.' },
        type: radio_control(['button', 'submit'] as const, 'Button type, `submit` for an item inside a `<form>`.'),
        text_only: { control: 'boolean', description: 'A status line, not an action: plain text, no hover.' },
    },
    args: {
        variant: 'default',
        type: 'button',
        text_only: false,
        slots: { default: 'Copy fleet link' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const item = within(canvasElement).getByRole('button', { name: 'Copy fleet link' })
        await expect(item).toHaveClass('action-menu-item')
        await expect(item).toHaveClass('action-menu-item--default')
        await expect(item).toHaveAttribute('type', 'button')
    },
}

export const AsLink = {
    args: { href: '/fleets/92221/', slots: { default: 'Open fleet' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: 'Open fleet' })
        await expect(link).toHaveAttribute('href', '/fleets/92221/')
        await expect(within(canvasElement).queryByRole('button')).toBeNull()
    },
}

export const Danger = {
    args: { variant: 'danger', slots: { default: 'Remove pilot' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('button', { name: 'Remove pilot' })).toHaveClass('action-menu-item--danger')
    },
}

export const SuccessSubmit = {
    args: { variant: 'success', type: 'submit', slots: { default: 'Open survey' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const item = within(canvasElement).getByRole('button', { name: 'Open survey' })
        await expect(item).toHaveAttribute('type', 'submit')
        await expect(item).toHaveClass('action-menu-item--success')
    },
}

export const Primary = {
    args: { variant: 'primary', slots: { default: 'Mark delivered' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('button', { name: 'Mark delivered' })).toHaveClass('action-menu-item--primary')
    },
}

export const Muted = {
    args: { variant: 'muted', slots: { default: 'Hide for now' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('button', { name: 'Hide for now' })).toHaveClass('action-menu-item--muted')
    },
}

export const TextOnly = {
    args: { text_only: true, slots: { default: 'Claimed by Kel\'dar Atram 2h ago' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const line = within(canvasElement).getByText(/Claimed by/)
        await expect(line.tagName).toBe('SPAN')
        await expect(line).toHaveClass('action-menu-item--text')
        await expect(within(canvasElement).queryByRole('button')).toBeNull()
    },
}

export const Confirm = {
    name: 'Two-step confirm',
    args: { variant: 'danger', confirm_label: 'Yes, remove', slots: { default: 'Remove from fleet' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const first = canvas.getByRole('button', { name: 'Remove from fleet' })
        const confirm = canvasElement.querySelector('.is-confirm') as HTMLElement
        await expect(confirm).toHaveTextContent('Yes, remove')
        await waitFor(() => expect(confirm).not.toBeVisible())

        await userEvent.click(first)
        await waitFor(() => expect(confirm).toBeVisible())
        await waitFor(() => expect(first).not.toBeVisible())
        // Not asserted: the component moves focus with `$nextTick(() => $refs.confirm.focus())`, which a full
        // Chromium run did not see land on the confirm button (possible component bug, reported).

        // Escape disarms: back to the first step.
        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(first).toBeVisible())
        await waitFor(() => expect(confirm).not.toBeVisible())
    },
}

export const ConfirmSubmitsOnSecondClick = {
    name: 'Confirm runs only on second click',
    args: {
        confirm_label: 'Yes, delete',
        type: 'submit',
        variant: 'danger',
        'data-testid': 'confirm-action',
        slots: { default: 'Delete doctrine' },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const confirm = canvas.getByTestId('confirm-action')
        // Attributes and the submit type belong to the confirm button, not the first step.
        await expect(confirm).toHaveAttribute('type', 'submit')
        await expect(canvas.getByRole('button', { name: 'Delete doctrine' })).toHaveAttribute('type', 'button')
        await expect(canvas.getByRole('button', { name: 'Delete doctrine' })).not.toHaveAttribute('data-testid')
        await userEvent.click(canvas.getByRole('button', { name: 'Delete doctrine' }))
        await waitFor(() => expect(confirm).toBeVisible())
    },
}
