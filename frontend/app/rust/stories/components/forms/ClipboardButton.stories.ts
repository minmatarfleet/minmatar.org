import { expect, userEvent, waitFor, within } from 'storybook/test'
import ClipboardButton from '@components/blocks/ClipboardButton.astro'
import { BUTTON_SIZES, radio_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

const FIT = '[Rifter, Minmatar Fleet Rifter]\n200mm Autocannon II\n1MN Afterburner II\nSmall Armor Repairer II'

export default {
    title: 'Components/Forms/ClipboardButton',
    component: ClipboardButton,
    parameters: {
        docs: {
            description: {
                component: [
                    'A small button that copies the text of a hidden, readonly `<textarea>` (rendered next to it, id = `id`) through the global `copyFitToClipboard()`. The label flips to "Copied" for two seconds. Put the text to copy in the default slot, or bind it with `x_value` for Alpine-driven content.',
                    'Used for fittings, links and Discord pings. `id` must be unique on the page. `source` tags the copy for analytics (`fitting_copied`). The copy itself needs the real clipboard API, so its play step is `browser`-only.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        id: { control: 'text', description: 'Id of the hidden textarea that holds the text to copy. Must be unique on the page.' },
        alert_prefix: { control: 'text', description: 'Text shown before the toast message ("<prefix> copied").' },
        narrow: { control: 'boolean', description: 'Less inline padding.' },
        size: radio_control(BUTTON_SIZES, 'Button size.'),
        text: { control: 'text', description: 'Label before copying. Defaults to the translated "Copy".' },
        copied_text: { control: 'text', description: 'Label after copying. Defaults to the translated "Copied".' },
        iconed: { control: 'boolean', description: 'Show the clipboard icon.' },
        x_value: { control: 'text', description: 'Alpine expression that supplies the copied text instead of the slot.' },
        source: { control: 'text', description: 'Analytics tag passed to `copyFitToClipboard`.' },
    },
    args: {
        id: 'fit-rifter',
        narrow: false,
        size: 'sm',
        iconed: true,
        slots: { default: FIT },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: /Copy/ })).toBeVisible()
        const textarea = canvasElement.querySelector('textarea#fit-rifter') as HTMLTextAreaElement
        await expect(textarea).not.toBeNull()
        await expect(textarea).toHaveAttribute('readonly')
        await expect(textarea).toHaveClass('hidden')
        await expect(textarea.value).toContain('Rifter')
    },
}

export const WithoutIcon = {
    args: { iconed: false },
    play: async ({ canvasElement }: Ctx) => {
        const button = within(canvasElement).getByRole('button')
        await expect(button.querySelector('svg')).toBeNull()
    },
}

export const IconedHasIcon = {
    name: 'With icon',
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('button').querySelector('svg')).not.toBeNull()
    },
}

export const CustomLabels = {
    args: { id: 'ping-text', text: 'Copy ping', copied_text: 'Ping copied', slots: { default: '@FL33T Rifter fleet forming in Amamake, 19:00 EVE' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('button', { name: /Copy ping/ })).toBeVisible()
        await expect(canvasElement.querySelector('textarea#ping-text')).not.toBeNull()
    },
}

export const Large = {
    args: { id: 'fit-stabber', size: 'lg', narrow: true, slots: { default: '[Stabber, Doctrine Stabber]' } },
    play: async ({ canvasElement }: Ctx) => {
        const button = within(canvasElement).getByRole('button')
        await expect(button).toHaveAttribute('data-size', 'lg')
        await expect(button).toHaveClass('narrow')
    },
}

export const Analytics = {
    name: 'Tagged for analytics (source)',
    args: { id: 'fit-tagged', alert_prefix: 'Fitting', source: 'doctrine_page' },
    play: async ({ canvasElement }: Ctx) => {
        const button = within(canvasElement).getByRole('button')
        await expect(button.getAttribute('x-on:click.stop.prevent')).toBe("copyFitToClipboard('fit-tagged', 'Fitting', 'doctrine_page')")
    },
}

export const ClickFlipsLabel = {
    name: 'Click flips the label to Copied',
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        // /js/clipboard.js (copyFitToClipboard) is loaded by the site layout, not by Storybook: stub it and record the call.
        const calls: unknown[][] = []
        ;(window as any).copyFitToClipboard = (...args: unknown[]) => { calls.push(args) }
        await userEvent.click(canvas.getByRole('button', { name: /Copy/ }))
        await expect(calls).toEqual([['fit-rifter']])
        await waitFor(() => expect(canvas.getByRole('button', { name: /Copied/ })).toBeVisible())
    },
}
