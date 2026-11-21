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
                    'Use `SwitchSquare` when the setting needs a title plus a description; use a plain `RadioCheckInput` for lists of options.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        checked: { control: 'boolean', description: 'Initial state, set on the native input.' },
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
