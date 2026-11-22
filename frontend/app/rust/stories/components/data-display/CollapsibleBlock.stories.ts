import { expect, userEvent, within, waitFor } from 'storybook/test'
import CollapsibleBlock from '@components/blocks/CollapsibleBlock.astro'
import { space_control } from '../../_controls'

const head = '<strong>Fleet rules</strong>'
const body = '<p>Stay on comms, align when told, and never warp off without the FC calling it.</p>'

export default {
    title: 'Components/Data display/CollapsibleBlock',
    component: CollapsibleBlock,
    parameters: {
        docs: {
            description: {
                component: [
                    'A section with a chevron header that shows or hides its body. Use it for secondary detail that should not push the page down (rules, long lists, advanced settings). The state lives in Alpine only: it does not load anything from the server, so lazy content belongs in an htmx partial inside the body.',
                    'The header button carries `aria-expanded`. `expanded` sets the initial state, `pre_chevron` moves the caret before the title.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        padding_inline: { control: 'text', description: 'Inline padding of the body.' },
        gap: space_control('Space between the header and the body.'),
        expanded: { control: 'boolean', description: 'Start open.' },
        id: { control: 'text', description: 'Id for the wrapper, so a link can scroll to it.' },
        pre_chevron: { control: 'boolean', description: 'Put the chevron before the header content.' },
    },
    args: {
        padding_inline: 'var(--space-3xs)',
        gap: 'var(--space-3xs)',
        expanded: false,
        pre_chevron: false,
        slots: { head, default: body },
    },
}

export const Collapsed = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const button = canvas.getByRole('button', { name: 'Fleet rules' })
        await waitFor(() => expect(button).toHaveAttribute('aria-expanded', 'false'))
        await expect(canvas.getByText(/Stay on comms/)).not.toBeVisible()
    },
}

export const Expanded = {
    args: { expanded: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const button = canvas.getByRole('button', { name: 'Fleet rules' })
        await waitFor(() => expect(button).toHaveAttribute('aria-expanded', 'true'))
        await expect(canvas.getByText(/Stay on comms/)).toBeVisible()
    },
}

export const ToggleWithClick = {
    name: 'Toggle with click',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const button = canvas.getByRole('button', { name: 'Fleet rules' })
        await waitFor(() => expect(button).toHaveAttribute('aria-expanded', 'false'))
        await userEvent.click(button)
        await waitFor(() => expect(button).toHaveAttribute('aria-expanded', 'true'))
        await userEvent.click(button)
        await waitFor(() => expect(button).toHaveAttribute('aria-expanded', 'false'))
        await waitFor(() => expect(canvas.getByText(/Stay on comms/)).not.toBeVisible())
    },
}

// x-collapse measures real layout, which happy-dom does not do, so the reveal is asserted in the browser.
export const RevealsBody = {
    name: 'Click reveals the body (browser)',
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/Stay on comms/)).not.toBeVisible()
        await userEvent.click(canvas.getByRole('button', { name: 'Fleet rules' }))
        await waitFor(() => expect(canvas.getByText(/Stay on comms/)).toBeVisible())
    },
}

export const PreChevron = {
    name: 'Pre-chevron',
    args: { pre_chevron: true, expanded: true, slots: { head: '<strong>Doctrine notes</strong>', default: '<p>Primary: Cormorant Navy Issue. Backup: Vexor Navy Issue.</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const button = canvas.getByRole('button', { name: 'Doctrine notes' })
        // With pre_chevron the caret svg is the first child inside the button.
        await expect(button.querySelector('svg')).toBeTruthy()
        await expect(canvas.getByText(/Primary: Cormorant/)).toBeVisible()
    },
}

export const WithId = {
    name: 'With id (linkable)',
    args: { id: 'srp-rules', expanded: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('#srp-rules')).toBeTruthy()
    },
}

export const PassesAttributesThrough = {
    name: 'Extra attributes and classes reach the root',
    args: { class: 'ml-auto', 'data-testid': 'collapsible-root', expanded: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const root = within(canvasElement).getByTestId('collapsible-root')
        await expect(root).toHaveClass('ml-auto')
        await expect(root).toHaveAttribute('x-data')
    },
}
