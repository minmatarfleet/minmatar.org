import { expect, within } from 'storybook/test'
import Button from '@components/blocks/Button.astro'
import FlagIcon from '@components/icons/FlagIcon.astro'
import { BUTTON_COLORS, BUTTON_SIZES, radio_control, select_control } from '../../_controls'

export default {
    title: 'Components/Forms/Button',
    component: Button,
    parameters: {
        docs: {
            description: {
                component: [
                    'The primary call to action. Renders an `<a>` when `href` is set and a `<button>` otherwise.',
                    'A `<button>` is rendered `disabled` and Alpine enables it on load (`x-init`), so it cannot be clicked before the page is interactive; pass `off_disable` to skip that, or `disabled` to keep it unavailable.',
                    '`external` links open a "leaving the website" dialog first. Reuse this component instead of styling a raw `<button>` (docs/frontend-design.md §4).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        color: select_control(BUTTON_COLORS, 'Background token. `transparent` keeps the border and uses `--highlight` text.'),
        size: radio_control(BUTTON_SIZES, '`sm` for dense rows and tables, `lg` everywhere else.'),
        href: { control: 'text', description: 'Renders an anchor instead of a button.' },
        narrow: { control: 'boolean', description: 'Less inline padding.' },
        centered: { control: 'boolean', description: 'Center the label and icon.' },
        disabled: { control: 'boolean', description: 'Unavailable: dimmed, `aria-disabled`, never enabled by Alpine.' },
        off_disable: { control: 'boolean', description: 'Render enabled from the server (no Alpine gate).' },
        new_tab: { control: 'boolean' },
        external: { control: 'boolean', description: 'Ask before leaving the site.' },
    },
    args: {
        color: 'fleet-red',
        size: 'lg',
        narrow: false,
        centered: true,
        disabled: false,
        off_disable: false,
        slots: { default: 'Join fleet' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const button = canvas.getByRole('button', { name: 'Join fleet' })
        await expect(button).toHaveClass('button')
        await expect(button).toHaveAttribute('data-size', 'lg')
        await expect(button.getAttribute('style')).toContain('var(--fleet-red)')
        // Alpine removes the load-time `disabled` once the page is interactive.
        await expect(button).toBeEnabled()
    },
}

export const Colors = {
    args: { color: 'alliance-blue', slots: { default: 'Alliance blue' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button')
        await expect(button.getAttribute('style')).toContain('var(--alliance-blue)')
        await expect(button.getAttribute('style')).toContain('var(--button-color)')
    },
}

export const Transparent = {
    args: { color: 'transparent', slots: { default: 'Cancel' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button', { name: 'Cancel' })
        await expect(button.getAttribute('style')).toContain('--inner_button_color: var(--highlight)')
    },
}

export const Small = {
    args: { size: 'sm', slots: { default: 'Edit' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('button')).toHaveAttribute('data-size', 'sm')
    },
}

export const Narrow = {
    args: { narrow: true, slots: { default: 'Narrow' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('button')).toHaveClass('narrow')
    },
}

export const WithIcon = {
    args: {
        slots: {
            icon: { component: FlagIcon },
            default: 'Report',
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button', { name: /Report/ })
        await expect(button.querySelector('svg')).not.toBeNull()
    },
}

export const Link = {
    args: { href: '/fleets/', slots: { default: 'Upcoming fleets' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: 'Upcoming fleets' })
        await expect(link).toHaveAttribute('href', '/fleets/')
        await expect(link).not.toHaveAttribute('target')
        await expect(link).not.toHaveAttribute('disabled')
    },
}

export const NewTab = {
    args: { href: '/doctrines/', new_tab: true, slots: { default: 'Doctrines' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link).toHaveAttribute('target', '_blank')
        await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    },
}

export const External = {
    args: { href: 'https://zkillboard.com/alliance/99011978/', external: true, slots: { default: 'zKillboard' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: 'zKillboard' })
        await expect(link).toHaveAttribute('target', '_blank')
        await expect(link).toHaveAttribute('rel', 'nofollow noopener noreferrer')
        await expect(link.getAttribute('x-data')).toContain('show_external_link_disclaimer')
    },
}

export const Disabled = {
    args: { disabled: true, slots: { default: 'Fleet full' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button', { name: 'Fleet full' })
        await expect(button).toBeDisabled()
        await expect(button).toHaveAttribute('aria-disabled', 'true')
        await expect(button).toHaveClass('is-disabled')
    },
}

export const EnabledWithoutAlpine = {
    name: 'Enabled without Alpine (off_disable)',
    args: { off_disable: true, slots: { default: 'Submit' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const button = within(canvasElement).getByRole('button')
        await expect(button).toBeEnabled()
        await expect(button).not.toHaveAttribute('x-init')
    },
}
