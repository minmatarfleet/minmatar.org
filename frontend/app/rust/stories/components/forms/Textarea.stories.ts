import { expect, userEvent, within } from 'storybook/test'
import Textarea from '@components/blocks/Textarea.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Forms/Textarea',
    component: Textarea,
    parameters: {
        docs: {
            description: {
                component: [
                    'The site multi-line field, styled like `Input`: bordered glass, vertical resize only. Every attribute (`name`, `rows`, `placeholder`, `maxlength`, `x-model`) passes to the `<textarea>`; the slot is its initial text.',
                    'Use it for notes, fleet descriptions and SRP details. For a borderless auto-growing field inside a chat-like composer use `StylessTextArea`. Pair with a `<label for>`; none is rendered.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        width: { control: 'text', description: 'Accepted for symmetry with `Input`; the field is always 100% wide.' },
        name: { control: 'text', description: 'Passed to the `<textarea>`.' },
        id: { control: 'text', description: 'Passed to the `<textarea>`.' },
        rows: { control: 'number', description: 'Visible lines.' },
        placeholder: { control: 'text', description: 'Passed to the `<textarea>`.' },
        maxlength: { control: 'number', description: 'Passed to the `<textarea>`.' },
        required: { control: 'boolean', description: 'Passed to the `<textarea>`.' },
        disabled: { control: 'boolean', description: 'Passed to the `<textarea>`.' },
        readonly: { control: 'boolean', description: 'Passed to the `<textarea>`.' },
    },
    args: {
        width: '100%',
        name: 'notes',
        id: 'notes',
        rows: 4,
        placeholder: 'What happened in the fight?',
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByPlaceholderText('What happened in the fight?')
        await expect(area.tagName).toBe('TEXTAREA')
        await expect(area).toHaveAttribute('rows', '4')
        await expect(area).toHaveAttribute('name', 'notes')
    },
}

export const AcceptsText = {
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByPlaceholderText('What happened in the fight?')
        await userEvent.type(area, 'Held the gate, lost two Rifters.')
        await expect(area).toHaveValue('Held the gate, lost two Rifters.')
    },
}

export const WithContent = {
    args: { slots: { default: 'Roam through Amamake, Rifters and Stabbers. Undock 19:00 EVE.' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByDisplayValue(/Undock 19:00 EVE/)).toBeVisible()
    },
}

export const Required = {
    args: { required: true, placeholder: 'Describe the loss' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByPlaceholderText('Describe the loss')).toBeRequired()
    },
}

export const Limited = {
    args: { maxlength: 20, placeholder: 'Short note' },
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByPlaceholderText('Short note') as HTMLTextAreaElement
        await expect(area).toHaveAttribute('maxlength', '20')
        await userEvent.type(area, 'This text is much longer than twenty characters')
        await expect(area.value.length).toBeLessThanOrEqual(20)
    },
}

export const Disabled = {
    args: { disabled: true, slots: { default: 'Fleet closed, notes locked.' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByDisplayValue('Fleet closed, notes locked.')).toBeDisabled()
    },
}

export const ReadOnly = {
    args: { readonly: true, slots: { default: 'Doctrine notes are maintained by the doctrine team.' } },
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByDisplayValue(/doctrine team/)
        await expect(area).toHaveAttribute('readonly')
    },
}
