import { expect, within } from 'storybook/test'
import ExternalLink from '@components/blocks/ExternalLink.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Navigation/ExternalLink',
    component: ExternalLink,
    parameters: {
        docs: {
            description: {
                component: [
                    'A link to another website. It opens in a new tab with `rel="nofollow noopener noreferrer"` and, on click, asks "You\'re leaving our site" first via the page-level alert dialog (`show_alert_dialog`); pilots can tick "do not show again", which Alpine persists in local storage.',
                    'Use it for any off-site URL in prose (zKillboard, EVE University, Reddit). For a button-looking external link use `Button` with `external`. Without the root Alpine alert dialog on the page the click does nothing, so in Storybook the dialog itself is not available.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        href: { control: 'text', description: 'Destination URL; also the target of the accept button in the disclaimer.' },
        class: { control: 'text', description: 'Extra classes for the anchor.' },
    },
    args: {
        href: 'https://zkillboard.com/alliance/99011978/',
        slots: { default: 'Alliance on zKillboard' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link', { name: 'Alliance on zKillboard' })
        await expect(link).toHaveAttribute('href', 'https://zkillboard.com/alliance/99011978/')
        await expect(link).toHaveAttribute('target', '_blank')
        await expect(link).toHaveAttribute('rel', 'nofollow noopener noreferrer')
    },
}

export const Disclaimer = {
    name: 'Leaving-the-site disclaimer wiring',
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link')
        const data = link.getAttribute('x-data') as string
        await expect(data).toContain('hide_external_link_disclaimer: $persist(false)')
        await expect(data).toContain('show_external_link_disclaimer')
        await expect(data).toContain('accept_href: "https://zkillboard.com/alliance/99011978/"')
        await expect(data).toContain('/partials/external_link_disclaimer_dialog/')
        await expect(link.getAttribute('x-on:click.prevent')).toContain('window.open(')
    },
}

export const KillboardKillmail = {
    name: 'Killmail link',
    args: { href: 'https://zkillboard.com/kill/123456789/', slots: { default: 'Rifter loss, Amamake' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('link', { name: 'Rifter loss, Amamake' }))
            .toHaveAttribute('href', 'https://zkillboard.com/kill/123456789/')
    },
}

export const InProse = {
    name: 'Inline in prose',
    args: {
        href: 'https://wiki.eveuniversity.org/Frigates',
        slots: { default: 'EVE University frigate guide' },
        class: 'underline',
    },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link', { name: 'EVE University frigate guide' })
        await expect(link).toHaveClass('underline')
        await expect(link).toHaveAttribute('href', 'https://wiki.eveuniversity.org/Frigates')
    },
}

export const WithIconContent = {
    name: 'Wrapping an image',
    args: {
        href: 'https://www.reddit.com/r/Minmatar/',
        slots: { default: '<img src="/images/fleet-logo.png" alt="r/Minmatar" width="48" height="48" />' },
    },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link', { name: 'r/Minmatar' })
        await expect(link.querySelector('img')).not.toBeNull()
        await expect(link).toHaveAttribute('target', '_blank')
    },
}

export const PassthroughAttributes = {
    name: 'Attributes pass through',
    args: { 'data-testid': 'ext', title: 'Opens zKillboard' },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByTestId('ext')
        await expect(link).toHaveAttribute('title', 'Opens zKillboard')
    },
}
