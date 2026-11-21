import { expect, userEvent, within } from 'storybook/test'
import UnstyledRadioCheckButton from '@components/blocks/UnstyledRadioCheckButton.astro'
import { radio_control } from '../../_controls'

export default {
    title: 'Components/Forms/UnstyledRadioCheckButton',
    component: UnstyledRadioCheckButton,
    parameters: {
        docs: {
            description: {
                component: [
                    'A bare label wrapping a native radio or checkbox plus a `<small>` label, with no drawn box. The parent decides how the checked state looks (typically `label:has(input:checked)` styles, as on the blueprint sorting buttons).',
                    'Use it for segmented "pick one" button rows; use `RadioCheckInput` when you want the standard box.',
                    'Extra attributes (`x-model`, `x-on:change`, `value`, `name`) go to the input; `label` is required.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        type: radio_control(['checkbox', 'radio'], 'Native input type.'),
        label: { control: 'text', description: 'Text inside the label. Replaced by the default slot when given.' },
        name: { control: 'text', description: 'Passed to the input; radios with the same name form a group.' },
        value: { control: 'text', description: 'Passed to the input.' },
        checked: { control: 'boolean', description: 'Initial state.' },
        disabled: { control: 'boolean', description: 'Blocks interaction.' },
    },
    args: {
        type: 'radio',
        label: 'Best efficiency',
        name: 'sorting',
        value: 'best_efficiency',
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Best efficiency' })
        await expect(input).toHaveAttribute('value', 'best_efficiency')
        await expect(input.closest('label')).toHaveClass('cursor-pointer')
        // Unstyled: no drawn box element.
        await expect(canvasElement.querySelector('.box')).toBeNull()
    },
}

export const Selecting = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Best efficiency' })
        await expect(input).not.toBeChecked()
        await userEvent.click(within(canvasElement).getByText('Best efficiency'))
        await expect(input).toBeChecked()
    },
}

export const Checked = {
    args: { checked: true, label: 'Material efficiency', value: 'material_efficiency' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('radio', { name: 'Material efficiency' })).toBeChecked()
    },
}

export const Checkbox = {
    args: { type: 'checkbox', label: 'Show BPCs', name: 'show_bpcs', value: '1' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('checkbox', { name: 'Show BPCs' })
        await userEvent.click(input)
        await expect(input).toBeChecked()
        await userEvent.click(input)
        await expect(input).not.toBeChecked()
    },
}

export const Disabled = {
    args: { disabled: true, label: 'Time efficiency', value: 'time_efficiency' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Time efficiency' })
        await expect(input).toBeDisabled()
        await userEvent.click(input)
        await expect(input).not.toBeChecked()
    },
}
