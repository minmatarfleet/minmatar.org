import { expect, userEvent, within, waitFor } from 'storybook/test'
import CollapsableButton from '@components/blocks/CollapsableButton.astro'
import { BUTTON_COLORS, BUTTON_SIZES, radio_control, select_control } from '../../_controls'

export default {
    title: 'Components/Data display/CollapsableButton',
    component: CollapsableButton,
    parameters: {
        docs: {
            description: {
                component: [
                    'The header button behind CollapsibleBlock: a label with a caret that rotates with an Alpine `expanded` flag. It does not hold state itself; it expects an ancestor `x-data` with `expanded`, and the caller adds `x-on:click` to toggle it.',
                    '`appearance="plain"` is an unstyled text-and-caret row; `button` makes it look like a Button (`color`, `size`). Extra attributes pass to the `<button>`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        pre_chevron: { control: 'boolean', description: 'Caret before the label instead of after it.' },
        appearance: radio_control(['plain', 'button'], '`plain` is bare text; `button` looks like Button.'),
        color: select_control(BUTTON_COLORS, 'Background token when `appearance` is `button`.'),
        size: radio_control(BUTTON_SIZES, 'Button size when `appearance` is `button`.'),
    },
    args: {
        pre_chevron: false,
        appearance: 'plain',
        color: 'fleet-red',
        size: 'sm',
        // The caret reads `expanded` from an Alpine scope; the story puts one on the button itself.
        'x-data': '{ expanded: false }',
        'x-on:click': 'expanded = !expanded',
        slots: { default: 'Show fleet history' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button', { name: 'Show fleet history' })
        await expect(button).toHaveAttribute('type', 'button')
        await expect(button).toHaveAttribute('data-appearance', 'plain')
        await expect(button.querySelector('svg')).toBeTruthy()
    },
}

export const AsButton = {
    name: 'As button',
    args: { appearance: 'button', color: 'alliance-blue', size: 'lg' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button')
        await expect(button).toHaveAttribute('data-appearance', 'button')
        await expect(button).toHaveAttribute('data-size', 'lg')
        await expect(button.getAttribute('style')).toContain('var(--alliance-blue)')
        await expect(button.getAttribute('style')).toContain('var(--button-color)')
    },
}

export const TransparentButton = {
    name: 'Transparent button',
    args: { appearance: 'button', color: 'transparent' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button')
        await expect(button.getAttribute('style')).toContain('var(--highlight)')
        await expect(button).toHaveAttribute('data-size', 'sm')
    },
}

export const PreChevron = {
    name: 'Pre-chevron',
    args: { pre_chevron: true, slots: { default: 'Doctrine fits' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button', { name: 'Doctrine fits' })
        await expect(button.querySelector('svg')).toBeTruthy()
        // The caret comes before the label: it is the first element child of the inner row.
        await expect(button.querySelector('svg')?.parentElement?.firstElementChild?.tagName.toLowerCase()).toBe('svg')
    },
}

export const ClickToggle = {
    name: 'Click toggles the caret (Alpine)',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button')
        const caret = button.querySelector('svg') as SVGElement
        await waitFor(() => expect(caret).toHaveClass('collapsed'))
        await userEvent.click(button)
        await waitFor(() => expect(caret).toHaveClass('expanded'))
        await userEvent.click(button)
        await waitFor(() => expect(caret).toHaveClass('collapsed'))
    },
}
