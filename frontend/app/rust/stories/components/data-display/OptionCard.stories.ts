import { expect, within, userEvent, waitFor } from 'storybook/test'
import OptionCard from '@components/blocks/OptionCard.astro'
import { radio_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Data display/OptionCard',
    component: OptionCard,
    parameters: {
        docs: {
            description: {
                component: [
                    'One choice of a radio group (or a pick-many group with `type="checkbox"`), drawn as a card. The `<input>` is real and visually hidden, so arrow keys, Space and form submission work natively.',
                    'Use it for a handful of rich options (a mentor class, a time slot); for a long list use a select. The checked state is yellow; wire Alpine (`x-model`) or htmx (`hx-get`, `hx-trigger`) through `input_attributes`, not on the label.',
                    'Group them in a `<fieldset>` so the radios share a name and an accessible group label.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        name: { control: 'text', description: 'Input name; options of one group share it.' },
        value: { control: 'text', description: 'Input value submitted when chosen.' },
        type: radio_control(['radio', 'checkbox'] as const, '`radio` picks one of the group, `checkbox` lets pilots pick several.'),
        checked: { control: 'boolean', description: 'Server-rendered selected state.' },
        input_attributes: { control: 'object', description: 'Extra attributes for the `<input>`: `required`, `x-model`, `hx-*`, `disabled`.' },
    },
    args: {
        name: 'doctrine',
        value: 'rifter',
        type: 'radio',
        checked: false,
        input_attributes: {},
        slots: { default: '<strong>Rifter</strong>' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const input = canvas.getByRole('radio', { name: 'Rifter' })
        await expect(input).toHaveAttribute('name', 'doctrine')
        await expect(input).toHaveAttribute('value', 'rifter')
        await expect(input).not.toBeChecked()
        await expect(canvasElement.querySelector('label.option-card')).not.toBeNull()
        await userEvent.click(input)
        await expect(input).toBeChecked()
    },
}

export const Checked = {
    args: { checked: true },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('radio', { name: 'Rifter' })).toBeChecked()
    },
}

export const Checkbox = {
    name: 'Checkbox (pick many)',
    args: { type: 'checkbox', name: 'roles', value: 'logi', slots: { default: '<strong>Logistics</strong>' } },
    play: async ({ canvasElement }: Ctx) => {
        const box = within(canvasElement).getByRole('checkbox', { name: 'Logistics' })
        await userEvent.click(box)
        await expect(box).toBeChecked()
        await userEvent.click(box)
        await expect(box).not.toBeChecked()
    },
}

export const RichContent = {
    name: 'Rich content with hint',
    args: {
        name: 'class_id',
        value: '12',
        checked: true,
        input_attributes: { required: true },
        slots: { default: '<span class="flex flex-col"><strong>Armor Tanking</strong><small>45 minutes · Discord voice</small></span>' },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const input = canvas.getByRole('radio', { name: /Armor Tanking/ })
        await expect(input).toBeRequired()
        await expect(input).toBeChecked()
        await expect(canvas.getByText('45 minutes · Discord voice')).toBeVisible()
    },
}

export const Disabled = {
    args: { input_attributes: { disabled: true }, slots: { default: '<strong>Fleet full</strong>' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('radio', { name: 'Fleet full' })).toBeDisabled()
    },
}

export const AlpineModel = {
    name: 'Alpine x-model',
    // The card's own label hosts the Alpine scope here; on a page the scope is the form or dialog around the group.
    args: {
        value: 'other',
        'x-data': "{ slot: '' }",
        'x-bind:data-picked': 'slot',
        input_attributes: { 'x-model': 'slot' },
        slots: { default: '<strong>Another time</strong>' },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const input = canvas.getByRole('radio', { name: /Another time/ })
        await expect(input).toHaveAttribute('x-model', 'slot')
        await userEvent.click(canvas.getByText('Another time'))
        await expect(input).toBeChecked()
        await waitFor(() => expect(canvasElement.querySelector('label')).toHaveAttribute('data-picked', 'other'))
    },
}

export const Passthrough = {
    name: 'Attributes and class on the label',
    args: { class: 'my-choice', 'data-testid': 'choice' },
    play: async ({ canvasElement }: Ctx) => {
        const label = within(canvasElement).getByTestId('choice')
        await expect(label.tagName).toBe('LABEL')
        await expect(label).toHaveClass('option-card', 'my-choice')
    },
}
