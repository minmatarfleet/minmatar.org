import { expect, userEvent, within } from 'storybook/test'
import SwitchSquare from '@components/blocks/SwitchSquare.astro'

export default {
    title: 'Components/Forms/SwitchSquare',
    component: SwitchSquare,
    parameters: {
        docs: {
            description: {
                component: [
                    'A square-knob toggle with a highlighted title and a small description beside it, for settings that need explaining (account preferences, dialog opt-outs).',
                    'Like `Switch`, extra attributes (`name`, `x-model`, `disabled`) go to the native checkbox. They are not repeated on the description, so an `id` is unique.',
                    'The input has no `aria-label`; its accessible name comes from the surrounding label, i.e. the title plus description.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        checked: { control: 'boolean', description: 'Initial state of the checkbox.' },
        label: { control: 'text', description: 'Highlighted title. `false` hides it.' },
        description: { control: 'text', description: 'Small text under the title. `false` hides it.' },
        name: { control: 'text', description: 'Passed to the input.' },
        disabled: { control: 'boolean', description: 'Passed to the input.' },
    },
    args: {
        checked: false,
        label: 'Create a timer',
        description: 'Adds the structure to the timer board for your alliance.',
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const toggle = canvas.getByRole('checkbox')
        await expect(toggle).not.toBeChecked()
        await expect(canvas.getByText('Create a timer')).toBeVisible()
        await expect(canvas.getByText('Adds the structure to the timer board for your alliance.')).toBeVisible()
        await expect(toggle.closest('label')).toHaveClass('switch')
    },
}

export const Checked = {
    args: {
        checked: true,
        label: 'Hide the external link warning',
        description: 'Can be restored from your account settings.',
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('checkbox')).toBeChecked()
    },
}

export const Toggling = {
    args: { name: 'create_timer' },
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

export const LabelOnly = {
    args: { description: false, label: 'Show my fleet history' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Show my fleet history')).toBeVisible()
        await expect(canvasElement.querySelector('small')).toBeNull()
    },
}

export const DescriptionOnly = {
    args: { label: false, description: 'Receive a Discord DM when an FC pings Strategic fleets.' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Receive a Discord DM when an FC pings Strategic fleets.')).toBeVisible()
        await expect(canvasElement.querySelector('.text-\\[var\\(--highlight\\)\\]')).toBeNull()
    },
}

export const Disabled = {
    args: { disabled: true, checked: true, label: 'Required by your corporation', description: 'Ask a director to change this.' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const toggle = within(canvasElement).getByRole('checkbox')
        await expect(toggle).toBeDisabled()
        await expect(toggle).toBeChecked()
    },
}

export const AttributesOnInputOnly = {
    args: { id: 'create_timer_toggle', name: 'create_timer' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('#create_timer_toggle')).toHaveLength(1)
        await expect(canvasElement.querySelector('#create_timer_toggle')?.tagName).toBe('INPUT')
        await expect(canvasElement.querySelector('small')).not.toHaveAttribute('name')
    },
}
