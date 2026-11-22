import { expect, userEvent, within } from 'storybook/test'
import Switch from '@components/blocks/Switch.astro'

export default {
    title: 'Components/Forms/Switch',
    component: Switch,
    parameters: {
        docs: {
            description: {
                component: [
                    'A toggle switch around a native `<input type="checkbox">`: the default slot is the label, to the left of the slider.',
                    'Every attribute besides the slot (`checked`, `name`, `disabled`, `x-model`, `hx-*`) goes straight to the input, so bind state with Alpine `x-model` (local UI state) or post it with htmx.',
                    '`shape="square"` is the square-knob variant for settings that need explaining: `label` is a highlighted title and `description` small text beside the toggle (account preferences, dialog opt-outs). Their text is not repeated on the input, so an `id` stays unique, and the accessible name is the title plus description.',
                    'Use a plain `RadioCheckInput` for lists of options.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        checked: { control: 'boolean', description: 'Initial state, set on the native input.' },
        shape: { control: 'inline-radio', options: ['round', 'square'], description: 'Round slider (default) or the square-knob variant.' },
        label: { control: 'text', description: 'Highlighted title, shown beside the slider. `false` hides it.' },
        description: { control: 'text', description: 'Small text under the title. `false` hides it.' },
        name: { control: 'text', description: 'Passed through to the input (any attribute is).' },
        disabled: { control: 'boolean', description: 'Passed through to the input: dims the switch and blocks clicks.' },
    },
    args: {
        checked: false,
        slots: { default: 'Fleet pings in Discord' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const toggle = canvas.getByRole('checkbox', { name: 'Fleet pings in Discord' })
        await expect(toggle).not.toBeChecked()
        await expect(toggle.closest('label')).toHaveClass('switch')
        await expect(toggle.closest('label')?.querySelector('.slider .circle')).not.toBeNull()
    },
}

export const Checked = {
    args: { checked: true, slots: { default: 'Show SRP-eligible ships only' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('checkbox', { name: 'Show SRP-eligible ships only' })).toBeChecked()
    },
}

export const Toggling = {
    args: { name: 'compressed', slots: { default: 'Compressed ore' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const toggle = within(canvasElement).getByRole('checkbox', { name: 'Compressed ore' })
        await expect(toggle).toHaveAttribute('name', 'compressed')
        await expect(toggle).not.toBeChecked()
        await userEvent.click(toggle)
        await expect(toggle).toBeChecked()
        await userEvent.click(toggle)
        await expect(toggle).not.toBeChecked()
    },
}

export const ClickingTheLabel = {
    name: 'Clicking the label text',
    args: { slots: { default: 'Use reprocessing implants' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await userEvent.click(canvas.getByText('Use reprocessing implants'))
        await expect(canvas.getByRole('checkbox')).toBeChecked()
    },
}

export const Disabled = {
    args: { disabled: true, checked: true, slots: { default: 'Locked by your corporation' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const toggle = within(canvasElement).getByRole('checkbox', { name: 'Locked by your corporation' })
        await expect(toggle).toBeDisabled()
        await userEvent.click(toggle)
        await expect(toggle).toBeChecked()
    },
}

export const BoundToAlpine = {
    name: 'Bound with x-model',
    args: {
        'x-data': '{ enabled: true }',
        'x-model': 'enabled',
        slots: { default: 'Notify me before fleets' },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const toggle = within(canvasElement).getByRole('checkbox', { name: 'Notify me before fleets' })
        await expect(toggle).toHaveAttribute('x-model', 'enabled')
        // Alpine initialises the input from the bound value, then follows clicks.
        await expect(toggle).toBeChecked()
        await userEvent.click(toggle)
        await expect(toggle).not.toBeChecked()
    },
}

const square_args = {
    shape: 'square',
    label: 'Create a timer',
    description: 'Adds the structure to the timer board for your alliance.',
    slots: {},
}

export const Square = {
    args: square_args,
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const toggle = canvas.getByRole('checkbox')
        await expect(toggle).not.toBeChecked()
        await expect(canvas.getByText('Create a timer')).toBeVisible()
        await expect(canvas.getByText('Adds the structure to the timer board for your alliance.')).toBeVisible()
        await expect(toggle.closest('label')).toHaveClass('switch')
        await expect(toggle.closest('label')).toHaveClass('switch--square')
    },
}

export const SquareChecked = {
    args: { ...square_args, checked: true, label: 'Hide the external link warning', description: 'Can be restored from your account settings.' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('checkbox')).toBeChecked()
    },
}

export const SquareToggling = {
    args: { ...square_args, name: 'create_timer' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const toggle = canvas.getByRole('checkbox')
        await expect(toggle).toHaveAttribute('name', 'create_timer')
        await userEvent.click(toggle)
        await expect(toggle).toBeChecked()
        await userEvent.click(canvas.getByText('Create a timer'))
        await expect(toggle).not.toBeChecked()
    },
}

export const SquareLabelOnly = {
    args: { ...square_args, description: false, label: 'Show my fleet history' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Show my fleet history')).toBeVisible()
        await expect(canvasElement.querySelector('small')).toBeNull()
    },
}

export const SquareDescriptionOnly = {
    args: { ...square_args, label: false, description: 'Receive a Discord DM when an FC pings Strategic fleets.' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Receive a Discord DM when an FC pings Strategic fleets.')).toBeVisible()
        await expect(canvasElement.querySelector('.text-\\[var\\(--highlight\\)\\]')).toBeNull()
    },
}

export const SquareDisabled = {
    args: { ...square_args, disabled: true, checked: true, label: 'Required by your corporation', description: 'Ask a director to change this.' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const toggle = within(canvasElement).getByRole('checkbox')
        await expect(toggle).toBeDisabled()
        await expect(toggle).toBeChecked()
    },
}

export const SquareAttributesOnInputOnly = {
    args: { ...square_args, id: 'create_timer_toggle', name: 'create_timer' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('#create_timer_toggle')).toHaveLength(1)
        await expect(canvasElement.querySelector('#create_timer_toggle')?.tagName).toBe('INPUT')
        await expect(canvasElement.querySelector('small')).not.toHaveAttribute('name')
    },
}
