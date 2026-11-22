import { expect, screen, userEvent, waitFor, within } from 'storybook/test'
import AlertDialog from '@components/blocks/AlertDialog.astro'
import PageScope from '../../../components/PageScope.astro'

// happy-dom (the vitest DOM) returns the server-rendered value from `getAttribute`/`classList` for attributes
// Alpine rebinds; the live attribute list is right there and in the browser.
const attr = (el: Element, name: string) => Array.from(el.attributes).find((a) => a.name === name)?.value

// Opens the dialog the way pages do: on the Alpine scope the layout puts on <body>.
const show = (canvasElement: HTMLElement, args: Record<string, unknown>) => {
    const scope = canvasElement.querySelector('[data-page-scope]')
    return (window as any).Alpine.$data(scope).show_alert_dialog(args)
}
const FULL = { title: 'Fleet is full', content: 'All 250 slots are taken. Try the next fleet.' }

export default {
    title: 'Components/Overlays/AlertDialog',
    component: AlertDialog,
    decorators: [PageScope],
    parameters: {
        docs: {
            description: {
                component: [
                    'The site-wide alert: one instance lives in the page layout and is driven from anywhere with `show_alert_dialog({ title, content, accept_label, cancel_label, show_cancel, accept_href, partial, hx })` on the body\'s Alpine scope. It returns a promise that resolves `true` when accepted and `false` when dismissed.',
                    'It renders a modal `dialog` named by its title and described by its content, traps focus while open and is `inert`/`aria-hidden` when closed. The backdrop and Escape close it (Escape clicks the backdrop). With `accept_href` the accept button is a real `target="_blank"` link, so the click stays a user gesture.',
                    'It has no props: it needs the `alert_dialog_*` state (`AlertDialogXData`). The stories use the `PageScope` decorator, which provides the same state the page layout does.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {},
    args: {},
}

const dialog = () => screen.getByRole('dialog', { hidden: true })

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(dialog()).toHaveAttribute('aria-hidden', 'true')
        await expect(canvas.queryByRole('dialog')).toBeNull()

        show(canvasElement, FULL)
        const open = await canvas.findByRole('dialog', { name: 'Fleet is full' })
        await expect(attr(open, 'class')).toContain('open')
        await expect(open).toHaveAttribute('aria-labelledby', 'alert-dialog-title')
        await waitFor(() => expect(within(open).getByText(FULL.content)).toBeVisible())
        await waitFor(() => expect(within(open).getByRole('button', { name: 'OK' })).toBeVisible())
        await expect(within(open).queryByRole('button', { name: 'Cancel' })).toBeNull()
    },
}

export const AcceptCloses = {
    name: 'OK closes the dialog and resolves true',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, FULL)
        const open = await canvas.findByRole('dialog', { name: 'Fleet is full' })
        await userEvent.click(within(open).getByRole('button', { name: 'OK' }))
        await expect(await result).toBe(true)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
        await expect(dialog()).toHaveAttribute('aria-hidden', 'true')
    },
}

export const BackdropCloses = {
    name: 'Backdrop click dismisses (false)',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, { title: 'SRP request denied', content: 'The loss was outside the doctrine.' })
        await canvas.findByRole('dialog', { name: 'SRP request denied' })
        const backdrop = canvasElement.querySelector('.alert-dialog-backdrop') as HTMLElement
        await expect(attr(backdrop, 'class')).toContain('open')
        await userEvent.click(backdrop)
        await expect(await result).toBe(false)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
        await expect(attr(backdrop, 'class')).not.toContain('open')
    },
}

export const WithCancel = {
    name: 'Accept and cancel labels',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, { title: 'Open killmail', content: 'zKillboard opens in a new tab.', accept_label: 'Open it', cancel_label: 'Stay here', show_cancel: true })
        const open = await canvas.findByRole('dialog', { name: 'Open killmail' })
        await waitFor(() => expect(within(open).getByRole('button', { name: 'Open it' })).toBeVisible())
        await waitFor(() => expect(within(open).getByRole('button', { name: 'Stay here' })).toBeVisible())
        await userEvent.click(within(open).getByRole('button', { name: 'Stay here' }))
        await expect(await result).toBe(false)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
    },
}

export const AcceptLink = {
    name: 'Accept as a new-tab link',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        show(canvasElement, { title: 'Leaving the website', content: 'zkillboard.com is not run by Minmatar Fleet.', accept_href: 'https://zkillboard.com/alliance/99011978/' })
        const open = await canvas.findByRole('dialog', { name: 'Leaving the website' })
        await waitFor(() => expect(open.querySelector('a[alert-dialog-action="accept"]')).not.toBeNull())
        const link = open.querySelector('a[alert-dialog-action="accept"]') as HTMLElement
        await expect(link).toHaveTextContent('Open')
        await expect(attr(link, 'href')).toBe('https://zkillboard.com/alliance/99011978/')
        await expect(link).toHaveAttribute('target', '_blank')
        await waitFor(() => expect(within(open).getByRole('button', { name: 'Cancel' })).toBeVisible())
    },
}

export const EscapeCloses = {
    name: 'Escape dismisses',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, FULL)
        await canvas.findByRole('dialog', { name: 'Fleet is full' })
        await userEvent.keyboard('{Escape}')
        await expect(await result).toBe(false)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
    },
}

export const TranslatedFallbackLabels = {
    name: 'Fallback labels are the translated strings',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // The `x-text` fallbacks were hard-coded English ('OK', 'Cancel', 'Open') that
        // replaced the server-rendered `t()` labels as soon as Alpine started.
        const labels = Array.from(canvasElement.querySelectorAll('[alert-dialog-action] span[x-text]'))
            .map((el) => attr(el, 'x-text') ?? '')
        await expect(labels).toHaveLength(3)
        await expect(labels.some((x) => x.endsWith('|| "Open"'))).toBe(true)
        await expect(labels.some((x) => x.endsWith('|| "OK"'))).toBe(true)
        await expect(labels.some((x) => x.endsWith('|| "Cancel"'))).toBe(true)
        await expect(labels.some((x) => x.includes("'"))).toBe(false)
    },
}
