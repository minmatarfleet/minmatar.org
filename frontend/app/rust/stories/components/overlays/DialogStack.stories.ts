import { expect, screen, userEvent, waitFor, within } from 'storybook/test'
import DialogStack from '../../../components/DialogStack.astro'
import PageScope from '../../../components/PageScope.astro'

// happy-dom (the vitest DOM) returns the server-rendered value from `getAttribute`/`classList` for attributes
// Alpine rebinds; the live attribute list is right there and in the browser.
const attr = (el: Element, name: string) => Array.from(el.attributes).find((a) => a.name === name)?.value

// The DialogButton's dialog is teleported to <body>; the site-wide ones stay in the story.
const button_dialog = () => document.querySelector('.button-dialog') as HTMLElement
const is_open = (el: Element | null) => !!el && (attr(el, 'class') ?? '').split(' ').includes('open')

export default {
    title: 'Components/Overlays/DialogStack',
    component: DialogStack,
    decorators: [PageScope],
    parameters: {
        docs: {
            description: {
                component: [
                    'A `DialogButton` dialog with the site-wide `Modal`, `AlertDialog` and `ConfirmDialog` opened from inside it, the way a page opens a preview or a confirmation from an edit form.',
                    'A site-wide dialog closes only itself: Escape, its backdrop and its buttons leave the dialog underneath open. Story-only wrapper (a story renders one component); it demonstrates `DialogBase`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {},
    args: {},
}

const open_button_dialog = async (canvasElement: HTMLElement) => {
    await userEvent.click(within(canvasElement).getByRole('button', { name: 'Edit fleet' }))
    return screen.findByRole('dialog', { name: undefined, hidden: false })
}

export const ModalOverButtonDialog = {
    name: 'Modal closes only itself on Escape',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await open_button_dialog(canvasElement)
        await waitFor(() => expect(is_open(button_dialog())).toBe(true))

        await userEvent.click(within(button_dialog()).getByRole('button', { name: 'Preview fleet' }))
        await waitFor(() => expect(canvas.getByText(/form up in Amamake/)).toBeVisible())

        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(is_open(canvasElement.querySelector('.modal .dialog'))).toBe(false))
        await expect(is_open(button_dialog())).toBe(true)
    },
}

export const ModalBackdropOverButtonDialog = {
    name: 'Modal backdrop leaves the dialog underneath open',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await open_button_dialog(canvasElement)
        await userEvent.click(within(button_dialog()).getByRole('button', { name: 'Preview fleet' }))
        await waitFor(() => expect(is_open(canvasElement.querySelector('.modal .dialog'))).toBe(true))

        await userEvent.click(canvasElement.querySelector('.modal-backdrop') as HTMLElement)
        await waitFor(() => expect(is_open(canvasElement.querySelector('.modal .dialog'))).toBe(false))
        await expect(is_open(button_dialog())).toBe(true)
    },
}

export const ConfirmOverButtonDialog = {
    name: 'Confirm answers without closing the dialog underneath',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await open_button_dialog(canvasElement)
        await userEvent.click(within(button_dialog()).getByRole('button', { name: 'Cancel fleet' }))
        const confirm = await canvas.findByRole('dialog', { name: 'Cancel fleet?' })
        await userEvent.click(within(confirm).getByRole('button', { name: 'No' }))
        await waitFor(() => expect(is_open(canvasElement.querySelector('.confirm-dialog .dialog'))).toBe(false))
        await expect(is_open(button_dialog())).toBe(true)
    },
}
