import { expect, within } from 'storybook/test'
import Markdown from '@components/blocks/Markdown.astro'
import { radio_control } from '../../_controls'

const doc = `## Fleet rules

Read this **before** you undock. See the [doctrine page](/doctrines/) or the [wiki](https://wiki.example.org/fleets).

- Join comms
- Fit the doctrine hull
- Ask the FC if unsure

1. Form up in Hek
2. Warp to the first beacon

Use \`/fleet join\` in Discord, then:

\`\`\`
align to celestial
\`\`\``

export default {
    title: 'Components/Data display/Markdown',
    component: Markdown,
    parameters: {
        docs: {
            description: {
                component: 'Renders a Markdown string to HTML on the server with the site\'s marked renderer. Use it for FC- and admin-written text (fleet notes, post bodies). Block mode wraps the output in a Flexblock (or a `div`); `inline` renders a single element with line breaks kept. External links get the leave-site disclaimer, and `open_in_new_tab` makes internal links open in a new tab. The markdown is not sanitized, so only pass trusted content.',
            },
        },
    },
    argTypes: {
        markdown: { control: 'text', description: 'The Markdown source.' },
        inline: { control: 'boolean', description: 'Render inline markup only, inside `inline_element`.' },
        inline_element: radio_control(['p', 'span', 'small'], 'Wrapper element in inline mode.'),
        element: radio_control(['div', 'Flexblock'], 'Wrapper for block mode (defaults to the Flexblock component).'),
        open_in_new_tab: { control: 'boolean', description: 'Open links in a new tab.' },
    },
    args: { markdown: doc, inline: false, inline_element: 'p', open_in_new_tab: false },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 2, name: 'Fleet rules' })).toBeVisible()
        await expect(canvas.getAllByRole('listitem').length).toBeGreaterThanOrEqual(5)
        await expect(canvas.getByRole('link', { name: 'doctrine page' })).toHaveAttribute('href', '/doctrines/')
        await expect(canvas.getByText('Fit the doctrine hull')).toBeVisible()
        await expect(canvasElement.querySelector('strong')?.textContent).toBe('before')
        await expect(canvasElement.querySelector('code')).toBeTruthy()
        await expect(canvasElement.querySelector('pre')?.textContent).toContain('align to celestial')
    },
}

export const Inline = {
    args: { inline: true, markdown: 'Next form-up **20:00 EVE** in [Hek](/fleets/)\nBring a Rifter' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('p')).toBeTruthy()
        await expect(canvasElement.querySelector('h2')).toBeNull()
        await expect(canvasElement.querySelector('strong')?.textContent).toBe('20:00 EVE')
        // breaks: true turns the newline into <br>
        await expect(canvasElement.querySelector('br')).toBeTruthy()
    },
}

export const InlineSmall = {
    name: 'Inline as small',
    args: { inline: true, inline_element: 'small', markdown: 'Updated by *Kel\'dar Atram*' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('small')).toBeTruthy()
        await expect(canvasElement.querySelector('em')?.textContent).toBe("Kel'dar Atram")
    },
}

export const InlineSpan = {
    name: 'Inline as span',
    args: { inline: true, inline_element: 'span', markdown: '38 pilots in **Fleet 94**' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('span')).toBeTruthy()
        await expect(canvasElement.querySelector('p')).toBeNull()
    },
}

export const Empty = {
    args: { markdown: '' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('h2, p, li')).toBeNull()
    },
}

export const ExternalLink = {
    name: 'External link',
    args: { markdown: 'Check the kill on [zKillboard](https://zkillboard.com/alliance/99011978/).' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: 'zKillboard' })
        await expect(link.getAttribute('x-data') ?? '').toContain('show_external_link_disclaimer')
    },
}
