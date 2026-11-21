import { expect, screen, userEvent, waitFor, within } from 'storybook/test'
import ConfirmDialog from '@components/blocks/ConfirmDialog.astro'
import PageScope from '../../../components/PageScope.astro'

// happy-dom (the vitest DOM) returns the server-rendered value from `getAttribute`/`classList` for attributes
// Alpine rebinds; the live attribute list is right there and in the browser.
const attr = (el: Element, name: string) => Array.from(el.attributes).find((a) => a.name === name)?.value

// Opens the dialog the way pages do: on the Alpine scope the layout puts on <body>. Resolves true/false.
const show = (canvasElement: HTMLElement, args: Record<string, unknown>) => {
    const scope = canvasElement.querySelector('[data-page-scope]')
    return (window as any).Alpine.$data(scope).show_confirm_dialog(args) as Promise<boolean>
}
const DOCTRINE = { title: 'Delete this doctrine?', content: 'Pilots will no longer see Rifter Fleet in the doctrine list.' }

export default {
    title: 'Components/Overlays/ConfirmDialog',
    component: ConfirmDialog,
    decorators: [PageScope],
    parameters: {
        docs: {
            description: {
                component: [
                    'The site-wide yes/no question: one instance in the page layout, driven by `show_confirm_dialog({ title, content, partial, accept_disabled, hx })` on the body\'s Alpine scope. The returned promise resolves `true` on Yes and `false` on No, the backdrop or Escape.',
                    'Use it for destructive or irreversible actions where the caller wants the answer back; use `AlertDialog` for a notice and `DialogButton` for a form. With `hx` the Yes button performs the htmx request itself; with `partial` the body is loaded from that URL.',
                    'It has no props: it needs the `confirm_dialog_*` state (`ConfirmDialogXData`). The stories use the `PageScope` decorator, which provides the same state the page layout does.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {},
    args: {},
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(screen.getByRole('dialog', { hidden: true })).toHaveAttribute('aria-hidden', 'true')
        await expect(canvas.queryByRole('dialog')).toBeNull()

        show(canvasElement, DOCTRINE)
        const open = await canvas.findByRole('dialog', { name: DOCTRINE.title })
        await expect(attr(open, 'class')).toContain('open')
        await expect(open).toHaveAttribute('aria-labelledby', 'confirm-dialog-title')
        await waitFor(() => expect(within(open).getByText(/no longer see Rifter Fleet/)).toBeVisible())
        await waitFor(() => expect(within(open).getByRole('button', { name: 'Yes' })).toBeVisible())
        await expect(within(open).getByRole('button', { name: 'No' })).toBeInTheDocument()
    },
}

export const Confirm = {
    name: 'Yes resolves true',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, DOCTRINE)
        const open = await canvas.findByRole('dialog', { name: DOCTRINE.title })
        await userEvent.click(within(open).getByRole('button', { name: 'Yes' }))
        await expect(await result).toBe(true)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
    },
}

export const Cancel = {
    name: 'No resolves false',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, DOCTRINE)
        const open = await canvas.findByRole('dialog', { name: DOCTRINE.title })
        await userEvent.click(within(open).getByRole('button', { name: 'No' }))
        await expect(await result).toBe(false)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
    },
}

export const BackdropCancels = {
    name: 'Backdrop click cancels',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, DOCTRINE)
        await canvas.findByRole('dialog', { name: DOCTRINE.title })
        await userEvent.click(canvasElement.querySelector('.confirm-dialog-backdrop') as HTMLElement)
        await expect(await result).toBe(false)
    },
}

export const EscapeCancels = {
    name: 'Escape cancels',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, DOCTRINE)
        await canvas.findByRole('dialog', { name: DOCTRINE.title })
        await userEvent.keyboard('{Escape}')
        await expect(await result).toBe(false)
    },
}

export const AcceptDisabled = {
    name: 'Yes disabled until ready',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        show(canvasElement, { title: 'Remove Sneak from the fleet?', content: 'Type the fleet name to confirm.', accept_disabled: true })
        const open = await canvas.findByRole('dialog', { name: /Remove Sneak/ })
        await expect(within(open).getByRole('button', { name: 'Yes' })).toBeDisabled()
        await expect(within(open).getByRole('button', { name: 'No' })).toBeEnabled()
    },
}
