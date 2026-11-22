import { expect, screen, userEvent, waitFor, within } from 'storybook/test'
import Modal from '@components/blocks/Modal.astro'
import PageScope from '../../../components/PageScope.astro'

// happy-dom (the vitest DOM) returns the server-rendered value from `getAttribute`/`classList` for attributes
// Alpine rebinds; the live attribute list is right there and in the browser.
const attr = (el: Element, name: string) => Array.from(el.attributes).find((a) => a.name === name)?.value

// Opens the modal the way pages do: on the Alpine scope the layout puts on <body>.
const show = (canvasElement: HTMLElement, args: Record<string, unknown>, opener = 'show_modal') => {
    const scope = canvasElement.querySelector('[data-page-scope]')
    return (window as any).Alpine.$data(scope)[opener](args)
}
const FLEET = { content: '<h3>Rifter Fleet Friday</h3><p>FC: Sneak. Form up in Amamake at 19:00 EVE.</p>' }

export default {
    title: 'Components/Overlays/Modal',
    component: Modal,
    decorators: [PageScope],
    parameters: {
        docs: {
            description: {
                component: [
                    'The site-wide content modal: one instance in the page layout, opened with `show_modal({ content })` for inline HTML or `show_modal({ partial, partial_params })` to load a server-rendered partial through htmx (`hx-trigger="intersect once"`, GET without params, POST with them).',
                    'Use it for read-only detail views (a fleet, a killmail, a pilot card) opened from anywhere; use `DialogButton` when the trigger and its content belong together, and `ConfirmDialog` for yes/no. The corner button and the backdrop close it; Escape clicks the backdrop. Focus is trapped while open and the dialog is `inert` when closed.',
                    '`persistent` renders the twin the layout keeps for flows that must not be dismissed by a stray click (`show_persistent_modal`, state `persistent_modal_*`): the backdrop ignores clicks, Escape and the corner button still close it. Both are `DialogBase` underneath. The stories use the `PageScope` decorator, which provides the same state the page layout does.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        persistent: { control: 'boolean', description: 'Backdrop clicks do nothing; Escape and the corner button still close. Opened with `show_persistent_modal`.' },
    },
    args: { persistent: false },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(screen.getByRole('dialog', { hidden: true })).toHaveAttribute('aria-hidden', 'true')
        await expect(canvas.queryByRole('dialog')).toBeNull()

        show(canvasElement, FLEET)
        const open = await canvas.findByRole('dialog')
        await expect(attr(open, 'class')).toContain('open')
        await expect(open).toHaveAttribute('aria-describedby', 'modal-description')
        await waitFor(() => expect(within(open).getByRole('heading', { name: 'Rifter Fleet Friday' })).toBeVisible())
        await waitFor(() => expect(within(open).getByText(/Form up in Amamake/)).toBeVisible())
    },
}

export const CloseButton = {
    name: 'Corner button closes',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, FLEET)
        const open = await canvas.findByRole('dialog')
        await userEvent.click(open.querySelector('[modal-action="cancel"]') as HTMLElement)
        await expect(await result).toBe(false)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
        await expect(screen.getByRole('dialog', { hidden: true })).toHaveAttribute('aria-hidden', 'true')
    },
}

export const BackdropCloses = {
    name: 'Backdrop click closes',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        show(canvasElement, FLEET)
        await canvas.findByRole('dialog')
        const backdrop = canvasElement.querySelector('.modal-backdrop') as HTMLElement
        await expect(attr(backdrop, 'class')).toContain('open')
        await userEvent.click(backdrop)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
        await expect(attr(backdrop, 'class')).not.toContain('open')
    },
}

export const EscapeCloses = {
    name: 'Escape closes',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        show(canvasElement, FLEET)
        await canvas.findByRole('dialog')
        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
    },
}

export const PartialLoading = {
    name: 'Loads a partial through htmx',
    // The modal fetches the partial with htmx once it intersects; that needs the browser.
    tags: ['browser'],
    parameters: {
        htmx: {
            '/partials/fleet_summary_component': { body: '<h3>Stratop Fleet</h3><p>24 pilots, 61 kills.</p>', delay: 300 },
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        show(canvasElement, { partial: '/partials/fleet_summary_component' })
        const open = await canvas.findByRole('dialog')
        await waitFor(() => expect(within(open).getByRole('heading', { name: 'Stratop Fleet' })).toBeVisible(), { timeout: 4000 })
        await expect(within(open).getByText(/61 kills/)).toBeVisible()
        await expect((window as any).__rust_htmx_requests.some((r: any) => JSON.stringify(r).includes('fleet_summary_component'))).toBe(true)
    },
}

export const Persistent = {
    name: 'Persistent ignores backdrop clicks',
    args: { persistent: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        let settled = false
        const result = show(canvasElement, FLEET, 'show_persistent_modal').then((value: unknown) => { settled = true; return value })
        const open = await canvas.findByRole('dialog')
        await expect(open).toHaveAttribute('aria-describedby', 'persistent-modal-description')

        const backdrop = canvasElement.querySelector('.persistent-modal-backdrop') as HTMLElement
        await expect(backdrop.hasAttribute('persistent-modal-action')).toBe(false)
        await userEvent.click(backdrop)
        await new Promise((resolve) => setTimeout(resolve, 50))
        await expect(settled).toBe(false)
        await expect(canvas.getByRole('dialog')).toBeVisible()

        await userEvent.keyboard('{Escape}')
        await expect(await result).toBe(false)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
    },
}

export const PersistentCornerButton = {
    name: 'Persistent closes from the corner button',
    args: { persistent: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = show(canvasElement, FLEET, 'show_persistent_modal')
        const open = await canvas.findByRole('dialog')
        await userEvent.click(open.querySelector('[persistent-modal-action="cancel"]') as HTMLElement)
        await expect(await result).toBe(false)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
    },
}

export const FocusReturns = {
    name: 'Focus returns to the trigger',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const trigger = document.createElement('button')
        trigger.textContent = 'Open fleet'
        canvasElement.prepend(trigger)
        trigger.focus()

        show(canvasElement, FLEET)
        const open = await canvas.findByRole('dialog')
        await waitFor(() => expect(open.contains(document.activeElement)).toBe(true))

        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
        await waitFor(() => expect(document.activeElement).toBe(trigger))
    },
}
