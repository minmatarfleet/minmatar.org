import { expect, within } from 'storybook/test'
import TextGroup from '@components/blocks/TextGroup.astro'
import { space_control } from '../../_controls'

export default {
    title: 'Components/Data display/TextGroup',
    component: TextGroup,
    parameters: {
        docs: {
            description: {
                component: 'A heading plus a paragraph stacked with a tight gap. Use it for a labeled value or short explanation inside a larger layout. The default slot goes in a `<p>` that takes the extra attributes; the `outside` slot replaces that paragraph when you need lists or several elements. `title` is `false` to hide the heading.',
            },
        },
    },
    argTypes: {
        title: { control: 'text', description: 'Heading (rendered as `<h4>`); `false` for none.' },
        gap: space_control('Space between the heading and the text.'),
        full: { control: 'boolean', description: 'Stretch to the full width of the parent (`w-full`).' },
    },
    args: {
        title: 'Why we fly together',
        gap: 'var(--space-3xs)',
        full: false,
        slots: { default: 'Fleets are how the militia holds the line: one doctrine, one FC, one call at a time.' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 4, name: 'Why we fly together' })).toBeVisible()
        await expect(canvas.getByText(/one doctrine, one FC/)).toBeVisible()
    },
}

export const WithoutTitle = {
    name: 'Without title',
    args: { title: false },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).queryByRole('heading')).toBeNull()
        await expect(within(canvasElement).getByText(/one doctrine/)).toBeVisible()
    },
}

export const Full = {
    args: { full: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.w-full')).toBeTruthy()
    },
}

export const OutsideSlot = {
    name: 'Outside slot (custom body)',
    args: {
        title: 'Required skills',
        slots: { outside: '<ul><li>Medium Hybrid Turret V</li><li>Shield Management IV</li><li>Warp Drive Operation III</li></ul>' },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('listitem')).toHaveLength(3)
        // The outside slot replaces the paragraph.
        await expect(canvasElement.querySelector('p')).toBeNull()
    },
}

export const PassthroughAttributes = {
    name: 'Passthrough attributes on the paragraph',
    args: { 'data-testid': 'body', class: 'text-muted' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByTestId('body').tagName).toBe('P')
    },
}
