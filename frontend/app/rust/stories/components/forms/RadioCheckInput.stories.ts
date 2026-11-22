import { expect, userEvent, within } from 'storybook/test'
import RadioCheckInput from '@components/blocks/RadioCheckInput.astro'
import { radio_control } from '../../_controls'

export default {
    title: 'Components/Forms/RadioCheckInput',
    component: RadioCheckInput,
    parameters: {
        docs: {
            description: {
                component: [
                    'A styled checkbox or radio: the native input is hidden by the stylesheet and a `.box` element draws the state. Use it for filters, option lists and consent boxes.',
                    '`label` renders as `<small>`; pass the default slot instead for richer content (it replaces `label`). Everything else (`name`, `value`, `checked`, `disabled`, `x-model`) lands on the input.',
                    'When the whole label should look like a button, use `UnstyledRadioCheckButton` and style the label yourself.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        type: radio_control(['checkbox', 'radio'], 'Native input type.'),
        label: { control: 'text', description: 'Text next to the box, in a `<small>`. Ignored when the default slot is filled.' },
        name: { control: 'text', description: 'Passed to the input; radios sharing a name form a group.' },
        value: { control: 'text', description: 'Passed to the input.' },
        checked: { control: 'boolean', description: 'Initial state.' },
        disabled: { control: 'boolean', description: 'Blocks interaction.' },
    },
    args: {
        type: 'checkbox',
        label: 'Include Strategic fleets',
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const input = canvas.getByRole('checkbox', { name: 'Include Strategic fleets' })
        await expect(input).not.toBeChecked()
        await expect(input.parentElement?.querySelector('.box')).not.toBeNull()
        await expect(input.closest('label')).toHaveClass('cursor-pointer')
    },
}

export const CheckboxToggling = {
    name: 'Checkbox toggles',
    args: { name: 'doctrine_filter', value: 'logistics', label: 'Logistics doctrines' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('checkbox', { name: 'Logistics doctrines' })
        await expect(input).toHaveAttribute('name', 'doctrine_filter')
        await expect(input).toHaveAttribute('value', 'logistics')
        await userEvent.click(input)
        await expect(input).toBeChecked()
        await userEvent.click(input)
        await expect(input).not.toBeChecked()
    },
}

export const Radio = {
    args: { type: 'radio', name: 'fleet_type', value: 'strategic', label: 'Strategic' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Strategic' })
        await expect(input).toHaveAttribute('type', 'radio')
        await userEvent.click(input)
        await expect(input).toBeChecked()
        // A radio cannot be unchecked by clicking it again.
        await userEvent.click(input)
        await expect(input).toBeChecked()
    },
}

export const Checked = {
    args: { checked: true, label: 'I have read the SRP rules' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('checkbox', { name: 'I have read the SRP rules' })).toBeChecked()
    },
}

export const Disabled = {
    args: { disabled: true, checked: true, label: 'Doctrine fit required' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('checkbox', { name: 'Doctrine fit required' })
        await expect(input).toBeDisabled()
        await userEvent.click(input)
        await expect(input).toBeChecked()
    },
}

export const CustomLabelSlot = {
    name: 'Custom label (default slot)',
    args: {
        label: 'Ignored label',
        slots: { default: '<span>Muninn <small>Heavy Assault Cruiser</small></span>' },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('checkbox', { name: /Muninn/ })).toBeInTheDocument()
        await expect(canvas.queryByText('Ignored label')).toBeNull()
    },
}

export const CheckedLabelStyle = {
    name: 'Checked label turns bold',
    tags: ['browser'], // asserts the computed style from the component's CSS
    args: { label: 'I have read the SRP rules' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const label = canvasElement.querySelector('small') as HTMLElement
        const input = within(canvasElement).getByRole('checkbox')
        await expect(getComputedStyle(label).fontWeight).not.toBe('600')
        await userEvent.click(input)
        // `.box` sits between the input and the label, so the rule must be `:checked ~ small`.
        await expect(getComputedStyle(label).fontWeight).toBe('600')
    },
}
