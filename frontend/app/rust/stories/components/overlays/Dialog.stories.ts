import { expect, waitFor, within } from 'storybook/test'
import Dialog from '@components/blocks/Dialog.astro'
import Button from '@components/blocks/Button.astro'
import FlexInline from '@components/compositions/FlexInline.astro'

export default {
    title: 'Components/Overlays/Dialog',
    component: Dialog,
    parameters: {
        docs: {
            description: {
                component: [
                    'The dialog surface: panel, padding, close button and header/body/footer slots. It has no open/close logic of its own. `DialogButton`, `AlertDialog`, `ConfirmDialog` and `Modal` wrap it and add `open` classes, `aria-hidden`, focus trap and backdrop.',
                    'Use it directly only to build a new overlay. The close button calls `close_dialog()` on the enclosing Alpine scope, so the wrapper must define that function. Stories render it in its static state.',
                    '`thin` drops the header/footer layout for edge-to-edge content, `transparent` renders a darkened backdrop layer behind a see-through panel, and `full_screen` stretches the panel to the viewport height.',
                ].join('\n\n'),
            },
        },
        // The dialog is `position: fixed` when `fixed`; give the story a frame tall enough to show it.
        layout: 'fullscreen',
    },
    argTypes: {
        breakout: { control: 'boolean', description: 'Breakout stacking used by the site\'s overlay wrappers (positions the dialog above the page chrome).' },
        fixed: { control: 'boolean', description: 'Pin the dialog to the viewport (`position: fixed`).' },
        thin: { control: 'boolean', description: 'Minimal padding and no header/footer layout.' },
        non_centered: { control: 'boolean', description: 'Do not center the content block vertically.' },
        body_full_h: { control: 'boolean', description: 'Make the body area fill the dialog height.' },
        full_screen: { control: 'boolean', description: 'Stretch the dialog to the full viewport height.' },
        close_button: { control: 'boolean', description: 'Show the close button in the corner.' },
        class: { control: 'text', description: 'Extra classes. The dialog is invisible (`opacity: 0`, no pointer events) until it has the `open` class, which the wrapper components toggle; the stories pass `open` so the surface is visible.' },
        transparent: { control: 'boolean', description: 'See-through panel over a dark backdrop layer.' },
    },
    args: {
        class: 'open',
        breakout: false,
        // The component defaults to `fixed`; stories pin it off so several dialogs can share the docs page.
        fixed: false,
        thin: false,
        non_centered: true,
        body_full_h: false,
        full_screen: false,
        close_button: true,
        transparent: false,
        slots: {
            header: '<h3>Join Rifter Fleet Friday</h3>',
            default: '<p>Undock from Amamake at 19:00 EVE. Fit: Rifter, Fleet Rifter (Armor). Comms in the fleet voice channel.</p>',
            footer: { component: FlexInline, props: { justification: 'flex-end' }, slots: { default: [
                { component: Button, props: { size: 'sm' }, slots: { default: 'Join fleet' } },
            ] } },
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const dialog = canvas.getByRole('dialog')
        await expect(dialog).toHaveClass('dialog')
        await expect(dialog).toHaveClass('open')
        await expect(dialog).toHaveClass('non-centered')
        await waitFor(() => expect(within(dialog).getByRole('heading', { name: 'Join Rifter Fleet Friday' })).toBeVisible())
        await waitFor(() => expect(within(dialog).getByText(/Undock from Amamake/)).toBeVisible())
        await waitFor(() => expect(within(dialog).getByRole('button', { name: 'Join fleet' })).toBeVisible())
        // The corner close button is the first button.
        await expect(dialog.querySelector('.dialog-close')).not.toBeNull()
    },
}

export const WithoutCloseButton = {
    args: { close_button: false },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.dialog-close')).toBeNull()
        await waitFor(() => expect(within(canvasElement).getByRole('dialog')).toBeVisible())
    },
}

export const Thin = {
    args: { thin: true, slots: { default: '<p>Compact content with minimal padding: 24 pilots, 61 kills.</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const dialog = within(canvasElement).getByRole('dialog')
        await waitFor(() => expect(within(dialog).getByText(/24 pilots/)).toBeVisible())
        // Thin dialogs skip the header/footer layout.
        await expect(dialog.querySelector('.cover-body')).toBeNull()
        await expect(within(dialog).queryByRole('heading')).toBeNull()
    },
}

export const Fixed = {
    args: { fixed: true, breakout: true },
    parameters: { layout: 'fullscreen' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const dialog = within(canvasElement).getByRole('dialog')
        await expect(dialog).toHaveClass('fixed')
        await expect(dialog).toHaveClass('breakout')
    },
}

export const Transparent = {
    args: { transparent: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const dialog = within(canvasElement).getByRole('dialog')
        await expect(dialog).toHaveClass('transparent')
        // A darkened backdrop layer is rendered next to the dialog.
        await expect(canvasElement.querySelector('.transparent-dialog')).not.toBeNull()
    },
}

export const FullScreen = {
    args: { full_screen: true, body_full_h: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const dialog = within(canvasElement).getByRole('dialog')
        await expect(dialog).toHaveClass('min-h-full')
        await expect(dialog.querySelector('.cover-body')).toHaveClass('min-h-full')
    },
}

export const Centered = {
    args: { non_centered: false },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('dialog')).not.toHaveClass('non-centered')
    },
}
