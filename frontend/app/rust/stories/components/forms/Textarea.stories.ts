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
                    'Use it for notes, fleet descriptions and SRP details. For a borderless auto-growing field inside a chat-like composer use `variant="bare"`: no border or padding, it grows with its content up to about 132px and then scrolls, and the container supplies the chrome. Pair with a `<label for>`; none is rendered.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        variant: { control: 'inline-radio', options: ['default', 'bare'], description: 'The bordered field (default), or a borderless transparent one that grows with its content.' },
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

export const FocusRing = {
    name: 'Keyboard focus ring',
    tags: ['browser'], // asserts the computed style from the component's CSS
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const field = canvasElement.querySelector("textarea") as HTMLElement
        await expect(getComputedStyle(field).outlineStyle).toBe('none')
        field.focus()
        // Same double highlight outline as links (`a:focus-visible` in _global.scss).
        await expect(getComputedStyle(field).outlineStyle).toBe('double')
        await expect(getComputedStyle(field).outlineColor).not.toBe('rgba(0, 0, 0, 0)')
    },
}

export const WidthComesFromCss = {
    name: 'Always 100% wide, attributes reach the field',
    args: { maxlength: 200, 'data-testid': 'reply-field' },
    play: async ({ canvasElement }: Ctx) => {
        const field = within(canvasElement).getByTestId('reply-field')
        await expect(field.tagName).toBe('TEXTAREA')
        await expect(field).toHaveAttribute('maxlength', '200')
        // There is no `width` prop: the field is always as wide as its container.
        await expect(field).not.toHaveAttribute('width')
    },
}

// variant="bare": a borderless, transparent textarea that grows with its content
// (`field-sizing: content`) up to about 132px, then scrolls. It replaces StylessTextArea.
const bare_args = {
    variant: 'bare',
    name: 'reply',
    rows: 1,
    placeholder: 'Reply to the fleet commander',
}

export const Bare = {
    args: { ...bare_args },
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByPlaceholderText('Reply to the fleet commander')
        await expect(area.tagName).toBe('TEXTAREA')
        await expect(area).toHaveAttribute('name', 'reply')
    },
}

export const BareAcceptsText = {
    args: { ...bare_args },
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByPlaceholderText('Reply to the fleet commander')
        await userEvent.type(area, 'On grid in Amamake.')
        await expect(area).toHaveValue('On grid in Amamake.')
    },
}

export const BareWithContent = {
    args: { ...bare_args, slots: { default: 'Bring a Stabber or a Rifter, no capitals.' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByDisplayValue(/no capitals/)).toBeVisible()
    },
}

export const BareMultiLine = {
    args: { ...bare_args, rows: 3, slots: { default: 'Line one\nLine two\nLine three' } },
    play: async ({ canvasElement }: Ctx) => {
        const area = canvasElement.querySelector('textarea') as HTMLTextAreaElement
        await expect(area).toHaveAttribute('rows', '3')
        await expect(area.value.split('\n')).toHaveLength(3)
    },
}

export const BareLimited = {
    args: { ...bare_args, maxlength: 12, placeholder: 'Max 12' },
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByPlaceholderText('Max 12') as HTMLTextAreaElement
        await userEvent.type(area, 'far more than twelve characters')
        await expect(area.value.length).toBeLessThanOrEqual(12)
    },
}

export const BareDisabled = {
    args: { ...bare_args, disabled: true, slots: { default: 'Comments closed' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByDisplayValue('Comments closed')).toBeDisabled()
    },
}

export const BareFocusRing = {
    name: 'Bare: keyboard focus ring',
    args: { ...bare_args },
    tags: ['browser'], // asserts the computed style from the component's CSS
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const field = canvasElement.querySelector("textarea") as HTMLElement
        await expect(getComputedStyle(field).outlineStyle).toBe('none')
        field.focus()
        // Same double highlight outline as links (`a:focus-visible` in _global.scss).
        await expect(getComputedStyle(field).outlineStyle).toBe('double')
        await expect(getComputedStyle(field).outlineColor).not.toBe('rgba(0, 0, 0, 0)')
    },
}

export const BareWidthComesFromCss = {
    name: 'Bare: always 100% wide, attributes reach the field',
    args: { ...bare_args, maxlength: 200, 'data-testid': 'reply-field' },
    play: async ({ canvasElement }: Ctx) => {
        const field = within(canvasElement).getByTestId('reply-field')
        await expect(field.tagName).toBe('TEXTAREA')
        await expect(field).toHaveAttribute('maxlength', '200')
        // There is no `width` prop: the field is always as wide as its container.
        await expect(field).not.toHaveAttribute('width')
    },
}
