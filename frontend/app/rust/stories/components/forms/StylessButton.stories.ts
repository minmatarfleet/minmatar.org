import { expect, userEvent, within } from 'storybook/test'
import StylessButton from '@components/blocks/StylessButton.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Forms/StylessButton',
    component: StylessButton,
    parameters: {
        docs: {
            description: {
                component: [
                    'A button or link with the browser chrome stripped: no border, padding or background, text inherits the parent colour. Use it to make a whole card, row or icon clickable; use `Button` for a visible call to action.',
                    'Renders an `<a>` when `href` is set and a `<button>` otherwise. Any extra attribute (`x-on:click`, `aria-label`, `class`) passes straight through. `external` adds the Alpine "leaving the website" dialog and rewrites `x-on:click.prevent`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        href: { control: 'text', description: 'Renders an anchor instead of a button.' },
        external: { control: 'boolean', description: 'Open `href` in a new tab after the "leaving the website" dialog (skipped once the pilot has accepted it).' },
    },
    args: {
        external: false,
        slots: { default: 'Open fleet details' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const button = within(canvasElement).getByRole('button', { name: 'Open fleet details' })
        await expect(button.tagName).toBe('BUTTON')
        await expect(button).not.toHaveAttribute('href')
        await expect(button).not.toHaveAttribute('rel')
    },
}

export const Link = {
    args: { href: '/fleets/', slots: { default: 'Upcoming fleets' } },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link', { name: 'Upcoming fleets' })
        await expect(link).toHaveAttribute('href', '/fleets/')
        await expect(link).not.toHaveAttribute('x-data')
    },
}

export const External = {
    args: { href: 'https://zkillboard.com/alliance/99011978/', external: true, slots: { default: 'FL33T on zKillboard' } },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link', { name: 'FL33T on zKillboard' })
        await expect(link).toHaveAttribute('rel', 'nofollow noopener noreferrer')
        await expect(link.getAttribute('x-data')).toContain('show_external_link_disclaimer')
        await expect(link.getAttribute('x-on:click.prevent')).toContain('hide_external_link_disclaimer')
    },
}

export const WithClickHandler = {
    args: {
        'x-data': '{ pinned: false }',
        'x-on:click.prevent': 'pinned = !pinned',
        'x-bind:aria-pressed': 'pinned',
        slots: { default: 'Pin this doctrine' },
    },
    play: async ({ canvasElement }: Ctx) => {
        const button = within(canvasElement).getByRole('button', { name: 'Pin this doctrine' })
        await expect(button).toHaveAttribute('aria-pressed', 'false')
        await userEvent.click(button)
        await expect(button).toHaveAttribute('aria-pressed', 'true')
    },
}

export const WrappingContent = {
    args: {
        slots: {
            default: '<span class="text-[var(--highlight)]">Rattini Tribe</span> <span>A-RAT</span>',
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const button = within(canvasElement).getByRole('button')
        await expect(button).toHaveTextContent('Rattini Tribe A-RAT')
        await expect(button.querySelectorAll('span')).toHaveLength(2)
    },
}

export const BareXData = {
    args: { 'x-data': true, 'x-on:click': 'opened = true', slots: { default: 'Open details' } },
    play: async ({ canvasElement }: Ctx) => {
        // A bare `x-data` used to throw while rendering (`true.slice`).
        const button = within(canvasElement).getByRole('button', { name: 'Open details' })
        await expect(button).toHaveAttribute('x-data', '{}')
    },
}

export const ExternalHrefWithQuote = {
    args: { href: "https://example.com/it's?a=1", external: true, slots: { default: 'Quoted link' } },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link', { name: 'Quoted link' })
        // The href is JSON-encoded in the expressions, so the quote cannot end the string early.
        await expect(link.getAttribute('x-on:click.prevent')).toContain(`window.open("https://example.com/it's?a=1", '_blank')`)
        await expect(link.getAttribute('x-data')).toContain(`accept_href: "https://example.com/it's?a=1"`)
    },
}
