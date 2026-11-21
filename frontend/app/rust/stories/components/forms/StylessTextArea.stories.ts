import { expect, userEvent, within } from 'storybook/test'
import StylessTextArea from '@components/blocks/StylessTextArea.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Forms/StylessTextArea',
    component: StylessTextArea,
    parameters: {
        docs: {
            description: {
                component: [
                    'A borderless, transparent `<textarea>` that grows with its content (`field-sizing: content`) up to about 132px, then scrolls. Use it inside a container that supplies the border or background, such as a comment composer or an inline note on a card.',
                    'It has no border or padding of its own, so on its own it looks like plain text; use `Textarea` for a standalone field. Attributes (`name`, `placeholder`, `maxlength`, `x-model`) pass to the `<textarea>`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        width: { control: 'text', description: 'Accepted for symmetry with `Textarea`; the field is always 100% wide.' },
        name: { control: 'text', description: 'Passed to the `<textarea>`.' },
        placeholder: { control: 'text', description: 'Passed to the `<textarea>`.' },
        rows: { control: 'number', description: 'Minimum visible lines for browsers without `field-sizing`.' },
        maxlength: { control: 'number', description: 'Passed to the `<textarea>`.' },
        disabled: { control: 'boolean', description: 'Passed to the `<textarea>`.' },
    },
    args: {
        width: '100%',
        name: 'reply',
        rows: 1,
        placeholder: 'Reply to the fleet commander',
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByPlaceholderText('Reply to the fleet commander')
        await expect(area.tagName).toBe('TEXTAREA')
        await expect(area).toHaveAttribute('name', 'reply')
    },
}

export const AcceptsText = {
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByPlaceholderText('Reply to the fleet commander')
        await userEvent.type(area, 'On grid in Amamake.')
        await expect(area).toHaveValue('On grid in Amamake.')
    },
}

export const WithContent = {
    args: { slots: { default: 'Bring a Stabber or a Rifter, no capitals.' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByDisplayValue(/no capitals/)).toBeVisible()
    },
}

export const MultiLine = {
    args: { rows: 3, slots: { default: 'Line one\nLine two\nLine three' } },
    play: async ({ canvasElement }: Ctx) => {
        const area = canvasElement.querySelector('textarea') as HTMLTextAreaElement
        await expect(area).toHaveAttribute('rows', '3')
        await expect(area.value.split('\n')).toHaveLength(3)
    },
}

export const Limited = {
    args: { maxlength: 12, placeholder: 'Max 12' },
    play: async ({ canvasElement }: Ctx) => {
        const area = within(canvasElement).getByPlaceholderText('Max 12') as HTMLTextAreaElement
        await userEvent.type(area, 'far more than twelve characters')
        await expect(area.value.length).toBeLessThanOrEqual(12)
    },
}

export const Disabled = {
    args: { disabled: true, slots: { default: 'Comments closed' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByDisplayValue('Comments closed')).toBeDisabled()
    },
}
