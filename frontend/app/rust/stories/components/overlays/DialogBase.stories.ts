import { expect, userEvent, waitFor, within } from 'storybook/test'
import DialogBase from '@components/blocks/DialogBase.astro'
import Button from '@components/blocks/Button.astro'
import PageScope from '../../../components/PageScope.astro'

// happy-dom (the vitest DOM) returns the server-rendered value from `getAttribute`/`classList` for attributes
// Alpine rebinds; the live attribute list is right there and in the browser.
const attr = (el: Element, name: string) => Array.from(el.attributes).find((a) => a.name === name)?.value

const scope = (canvasElement: HTMLElement) => (window as any).Alpine.$data(canvasElement.querySelector('[data-page-scope]'))

export default {
    title: 'Components/Overlays/DialogBase',
    component: DialogBase,
    decorators: [PageScope],
    parameters: {
        docs: {
            description: {
                component: [
                    'The base under `AlertDialog`, `ConfirmDialog` and `Modal`: the backdrop, Escape, the focus trap (focus returns to the trigger), `role="dialog"` with `aria-modal`, the label and description wiring, the region a partial is swapped into and closing. Use those three; reach for `DialogBase` only to add another site-wide dialog.',
                    '`name` is the state prefix on the page scope (`<name>_open`, `<name>_content`, `<name>_partial`, ...) and `show_<name>()` opens it, returning a promise that settles on the first click on an element with a `<name-with-dashes>-action` attribute. `titled` adds a title and puts the default slot in a row of buttons below the content; without it the content is the whole dialog with a corner button. `persistent` makes the backdrop ignore clicks.',
                    'Partials arrive by htmx swap into the content region (`hx-trigger="intersect"`); `partial_once` loads each partial once per opening and `partial_params` lets the modal POST params. It needs the `<name>_*` state (`AlpineScripts`); the stories use the `PageScope` decorator, which provides it.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        name: { control: 'select', options: ['alert_dialog', 'confirm_dialog', 'modal', 'persistent_modal'], description: 'State prefix on the page scope.' },
        titled: { control: 'boolean', description: 'Title above the content, the slot as a button row below it.' },
        persistent: { control: 'boolean', description: 'Backdrop clicks do nothing.' },
        backdrop_action: { control: 'radio', options: ['close', 'cancel'], description: 'Value of the backdrop\'s action attribute.' },
        partial_once: { control: 'boolean', description: 'Load the partial once per opening.' },
        partial_params: { control: 'boolean', description: 'The partial may be POSTed with `<name>_partial_params`.' },
        close_button: { control: 'boolean', description: 'Corner close button of the Dialog.' },
        thin: { control: 'boolean', description: 'Minimal padding.' },
        max_width: { control: 'text', description: 'Dialog max width, set as `--dialog-max-width`.' },
    },
    args: {
        name: 'modal',
        titled: false,
        persistent: false,
        backdrop_action: 'cancel',
        partial_once: true,
        partial_params: true,
        close_button: true,
        thin: true,
        max_width: '750px',
    },
}

export const Untitled = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = scope(canvasElement).show_modal({ content: '<p>Rifter Fleet Friday</p>' })
        const open = await canvas.findByRole('dialog')
        await expect(open).toHaveAttribute('aria-modal', 'true')
        await expect(open).toHaveAttribute('aria-describedby', 'modal-description')
        await expect(open.hasAttribute('aria-labelledby')).toBe(false)
        // The dialog fades in: wait for it to be opaque.
        await waitFor(() => expect(within(open).getByText('Rifter Fleet Friday')).toBeVisible())

        await userEvent.click(canvasElement.querySelector('.modal-backdrop') as HTMLElement)
        await expect(await result).toBe(false)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
    },
}

export const Titled = {
    args: {
        name: 'confirm_dialog', titled: true, thin: false, partial_once: false, partial_params: false, max_width: '500px',
        slots: {
            default: [
                { component: Button, props: { size: 'sm', 'confirm-dialog-action': 'accept' }, slots: { default: 'Yes' } },
                { component: Button, props: { size: 'sm', 'confirm-dialog-action': 'cancel' }, slots: { default: 'No' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = scope(canvasElement).show_confirm_dialog({ title: 'Cancel fleet?', content: 'Pilots will be told.' })
        const open = await canvas.findByRole('dialog', { name: 'Cancel fleet?' })
        await expect(open).toHaveAttribute('aria-labelledby', 'confirm-dialog-title')
        await expect(open).toHaveAttribute('aria-describedby', 'confirm-dialog-description')

        const yes = within(open).getByRole('button', { name: 'Yes' })
        // A second click on accept finds the promise already settled.
        await userEvent.dblClick(yes)
        await expect(await result).toBe(true)
        await waitFor(() => expect(canvas.queryByRole('dialog')).toBeNull())
    },
}

export const Persistent = {
    args: { name: 'persistent_modal', persistent: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const result = scope(canvasElement).show_persistent_modal({ content: '<p>Sign the fleet rules</p>' })
        const open = await canvas.findByRole('dialog')
        const backdrop = canvasElement.querySelector('.persistent-modal-backdrop') as HTMLElement
        await expect(attr(backdrop, 'class')).toContain('open')

        await waitFor(() => expect(open).toBeVisible())
        await userEvent.click(backdrop)
        await expect(canvas.getByRole('dialog')).toBeVisible()

        await userEvent.click(open.querySelector('[persistent-modal-action="cancel"]') as HTMLElement)
        await expect(await result).toBe(false)
    },
}
