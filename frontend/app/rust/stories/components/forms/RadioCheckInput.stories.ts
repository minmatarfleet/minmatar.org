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
                    '`bare` drops the drawn box and leaves just the hidden input and the label text, for rows where the whole label looks like a button and the parent styles the checked state (`label:has(input:checked)`, as on the blueprint sorting buttons).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        bare: { control: 'boolean', description: 'No drawn box: only the hidden input and the label text.' },
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

// bare: a label around a native radio or checkbox plus a `<small>` label, with no
// drawn box, for segmented "pick one" rows where the parent styles the checked
// state (`label:has(input:checked)`). It replaces UnstyledRadioCheckButton.
const bare_args = {
    bare: true,
    type: 'radio',
    label: 'Best efficiency',
    name: 'sorting',
    value: 'best_efficiency',
}

export const BareDefault = {
    args: { ...bare_args },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Best efficiency' })
        await expect(input).toHaveAttribute('value', 'best_efficiency')
        await expect(input.closest('label')).toHaveClass('cursor-pointer')
        // bare: no drawn box element.
        await expect(canvasElement.querySelector('.box')).toBeNull()
    },
}

export const BareSelecting = {
    args: { ...bare_args },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Best efficiency' })
        await expect(input).not.toBeChecked()
        await userEvent.click(within(canvasElement).getByText('Best efficiency'))
        await expect(input).toBeChecked()
    },
}

export const BareChecked = {
    args: { ...bare_args, checked: true, label: 'Material efficiency', value: 'material_efficiency' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('radio', { name: 'Material efficiency' })).toBeChecked()
    },
}

export const BareCheckbox = {
    args: { ...bare_args, type: 'checkbox', label: 'Show BPCs', name: 'show_bpcs', value: '1' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('checkbox', { name: 'Show BPCs' })
        await userEvent.click(input)
        await expect(input).toBeChecked()
        await userEvent.click(input)
        await expect(input).not.toBeChecked()
    },
}

export const BareDisabled = {
    args: { ...bare_args, disabled: true, label: 'Time efficiency', value: 'time_efficiency' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Time efficiency' })
        await expect(input).toBeDisabled()
        await userEvent.click(input)
        await expect(input).not.toBeChecked()
    },
}
