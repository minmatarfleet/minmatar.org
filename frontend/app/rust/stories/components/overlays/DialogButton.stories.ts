import { expect, screen, userEvent, waitFor, within } from 'storybook/test'
import DialogButton from '@components/blocks/DialogButton.astro'
import Input from '@components/blocks/Input.astro'
import Button from '@components/blocks/Button.astro'
import { BUTTON_COLORS, BUTTON_SIZES, radio_control, select_control } from '../../_controls'

// happy-dom (the vitest DOM) returns the server-rendered value from `getAttribute`/`classList` for attributes
// Alpine rebinds; the live attribute list is right there and in the browser.
const attr = (el: Element, name: string) => Array.from(el.attributes).find((a) => a.name === name)?.value

const FLEET_FORM = [
    { component: Input, props: { name: 'name', value: 'Rifter Fleet Friday', 'aria-label': 'Fleet name' } },
    { component: Input, props: { name: 'doctrine', value: 'Fleet Rifter (Armor)', 'aria-label': 'Doctrine' } },
]

export default {
    title: 'Components/Overlays/DialogButton',
    component: DialogButton,
    parameters: {
        docs: {
            description: {
                component: [
                    'A button that opens its own dialog. The trigger is the default slot (a `Button`, or a bare `StylessButton` with `styless`), the dialog content is the `dialog` slot, with optional `header` and `footer` slots. The dialog is teleported to `<body>` (`x-teleport`), traps focus while open and is `inert` and `aria-hidden` when closed.',
                    'Use it when the trigger and its content belong together (an edit form, a details panel). For one shared prompt opened from anywhere use `AlertDialog`, `ConfirmDialog` or `Modal`. Load heavy content lazily with `LazyPartial` or `hx-trigger="intersect once"` inside the `dialog` slot; teleported content is processed by htmx when the dialog is created.',
                    'Escape, a click outside and the corner button close it. `disable_when_open` disables the trigger while the dialog is open (listens to `dialog_opened`/`dialog_closed`). Inside a Swiper pass `inside_swiper` so touch-drag is paused while open. If the `dialog` slot is missing a debug message is shown instead.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        size: radio_control(BUTTON_SIZES, 'Trigger button size.'),
        color: select_control(BUTTON_COLORS, 'Trigger button color.'),
        hidden: { control: 'boolean', description: 'Hide the trigger visually (the dialog is opened from elsewhere via its Alpine scope).' },
        narrow: { control: 'boolean', description: 'Less inline padding on the trigger.' },
        id: { control: 'text', description: 'Id for the trigger button.' },
        max_width: { control: 'text', description: 'Dialog max width, set as `--dialog-max-width`.' },
        inside_swiper: { control: 'boolean', description: 'Pause Swiper touch-drag while the dialog is open.' },
        thin_dialog: { control: 'boolean', description: 'Minimal padding, no header/footer layout.' },
        disable_when_open: { control: 'boolean', description: 'Disable the trigger while the dialog is open.' },
        non_centered: { control: 'boolean', description: 'Do not center the dialog content vertically.' },
        close_button: { control: 'boolean', description: 'Show the corner close button.' },
        full_screen: { control: 'boolean', description: 'Stretch the dialog to the full viewport height.' },
        body_full_h: { control: 'boolean', description: 'Make the body fill the dialog height.' },
        styless: { control: 'boolean', description: 'Render the trigger as an unstyled button instead of a `Button`.' },
        transparent: { control: 'boolean', description: 'See-through dialog over a dark backdrop layer.' },
    },
    args: {
        size: 'lg',
        color: 'green',
        hidden: false,
        narrow: false,
        max_width: '700px',
        inside_swiper: false,
        thin_dialog: false,
        disable_when_open: false,
        non_centered: true,
        close_button: true,
        full_screen: false,
        body_full_h: false,
        styless: false,
        transparent: false,
        slots: {
            default: 'Edit fleet',
            header: '<h3>Edit fleet</h3>',
            dialog: FLEET_FORM,
        },
    },
}

const dialog = () => screen.getByRole('dialog', { hidden: true })

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Edit fleet' })
        // Closed: teleported to the body, inert and hidden from assistive tech.
        await expect(canvasElement.contains(dialog())).toBe(false)
        await expect(dialog()).toHaveAttribute('aria-hidden', 'true')

        await userEvent.click(trigger)
        const open = await screen.findByRole('dialog')
        await expect(attr(open, 'class')).toContain('open')
        await waitFor(() => expect(within(open).getByRole('heading', { name: 'Edit fleet' })).toBeVisible())
        await expect(within(open).getByRole('textbox', { name: 'Fleet name' })).toHaveValue('Rifter Fleet Friday')
        await expect(open.getAttribute('style')).toContain('--dialog-max-width: 700px')
    },
}

export const CloseButton = {
    name: 'Corner button closes',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await userEvent.click(within(canvasElement).getByRole('button', { name: 'Edit fleet' }))
        const open = await screen.findByRole('dialog')
        await userEvent.click(open.querySelector('.dialog-close') as HTMLElement)
        await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
        await expect(dialog()).toHaveAttribute('aria-hidden', 'true')
    },
}

export const EscapeCloses = {
    name: 'Escape closes',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await userEvent.click(within(canvasElement).getByRole('button', { name: 'Edit fleet' }))
        await screen.findByRole('dialog')
        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    },
}

export const WithoutCloseButton = {
    args: { close_button: false },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await userEvent.click(within(canvasElement).getByRole('button', { name: 'Edit fleet' }))
        const open = await screen.findByRole('dialog')
        await expect(open.querySelector('.dialog-close')).toBeNull()
        // Escape still closes it.
        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    },
}

export const HeaderAndFooter = {
    args: {
        color: 'alliance-blue',
        slots: {
            default: 'Join fleet',
            header: '<h3>Join Stratop Fleet</h3>',
            dialog: '<p>Undock at 19:00 EVE. Fit: Stabber, Fleet Stabber (Shield). Join the fleet voice channel before undocking.</p>',
            footer: { component: Button, props: { size: 'sm' }, slots: { default: 'Confirm' } },
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Join fleet' })
        await expect(trigger.getAttribute('style')).toContain('var(--alliance-blue)')
        await userEvent.click(trigger)
        const open = await screen.findByRole('dialog')
        await waitFor(() => expect(within(open).getByRole('heading', { name: 'Join Stratop Fleet' })).toBeVisible())
        await waitFor(() => expect(within(open).getByText(/Undock at 19:00/)).toBeVisible())
        await waitFor(() => expect(within(open).getByRole('button', { name: 'Confirm' })).toBeVisible())
    },
}

export const ThinDialog = {
    args: {
        thin_dialog: true,
        max_width: '420px',
        slots: { default: 'Pilot card', dialog: '<p>Kel&#8217;dar Atram, Rattini Tribe (A-RAT).</p>' },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await userEvent.click(within(canvasElement).getByRole('button', { name: 'Pilot card' }))
        const open = await screen.findByRole('dialog')
        await waitFor(() => expect(within(open).getByText(/Rattini Tribe/)).toBeVisible())
        await expect(open.querySelector('.cover-body')).toBeNull()
        await expect(open.getAttribute('style')).toContain('--dialog-max-width: 420px')
    },
}

export const DisableWhenOpen = {
    args: { disable_when_open: true },
    // `dialog_opened`/`dialog_closed` are dispatched by dialog content; click-through only checks the wiring.
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const root = canvasElement.querySelector('[x-data]') as HTMLElement
        await expect(root.getAttribute('@dialog_opened.stop') ?? root.getAttribute('x-on:dialog_opened.stop')).toContain('setAttribute')
        await expect(root.getAttribute('@dialog_closed.stop') ?? root.getAttribute('x-on:dialog_closed.stop')).toContain('removeAttribute')
    },
}

export const Styless = {
    args: { styless: true, slots: { default: 'Fleet details', dialog: '<p>FC Sneak, 24 pilots, undock 19:00 EVE.</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Fleet details' })
        // No Button chrome: the trigger is a bare button.
        await expect(trigger).not.toHaveClass('button')
        await userEvent.click(trigger)
        await waitFor(() => expect(screen.getByText(/24 pilots/)).toBeVisible())
    },
}

export const SmallNarrowTrigger = {
    args: { size: 'sm', narrow: true, color: 'transparent', slots: { default: 'Details', dialog: '<p>Order #4412: 50x Rifter, contract to Amamake.</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const trigger = within(canvasElement).getByRole('button', { name: 'Details' })
        await expect(trigger).toHaveAttribute('data-size', 'sm')
        await expect(trigger).toHaveClass('narrow')
        await expect(trigger.getAttribute('style')).toContain('--inner_button_color: var(--highlight)')
    },
}

export const MissingDialogSlot = {
    name: 'Missing dialog slot shows a debug message',
    args: { slots: { default: 'Broken dialog' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await userEvent.click(within(canvasElement).getByRole('button', { name: 'Broken dialog' }))
        const open = await screen.findByRole('dialog')
        // The placeholder is rendered so a forgotten slot is obvious during development.
        await expect(open.querySelector('.cover-body')?.textContent?.trim().length).toBeGreaterThan(0)
    },
}

export const LazyContent = {
    name: 'Content loaded with htmx on open',
    tags: ['browser'],
    args: {
        slots: {
            default: 'Fleet roster',
            header: '<h3>Fleet roster</h3>',
            dialog: '<div hx-get="/partials/fleet_roster_component" hx-trigger="intersect once" hx-swap="innerHTML"><p>Loading...</p></div>',
        },
    },
    parameters: {
        htmx: { '/partials/fleet_roster_component': { body: '<ul><li>Kel&#8217;dar Atram (FC)</li><li>Sneak (Scout)</li></ul>', delay: 300 } },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await userEvent.click(within(canvasElement).getByRole('button', { name: 'Fleet roster' }))
        const open = await screen.findByRole('dialog')
        await waitFor(() => expect(within(open).getByText(/Sneak \(Scout\)/)).toBeVisible(), { timeout: 4000 })
        await expect((window as any).__rust_htmx_requests.length).toBeGreaterThan(0)
    },
}

export const NonCenteredFollowsProp = {
    name: 'non_centered is passed once and follows the prop',
    args: { non_centered: false },
    play: async () => {
        // `non_centered` used to be passed twice (true, then the prop); the prop is the single source.
        await expect(attr(dialog(), 'class')).not.toContain('non-centered')
    },
}
