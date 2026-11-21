import { expect, userEvent, within, waitFor } from 'storybook/test'
import ComponentBlockHeader from '@components/blocks/ComponentBlockHeader.astro'

// The component reads two Alpine globals that the site's page layout (Viewport.astro) defines. Alpine falls back to
// window for names it cannot find in a scope, so the story provides them the same way.
Object.assign(globalThis, { global_collapse: false, post_header_height: 0 })

const header = '<h3>Doctrine: Cormorant Navy Issue</h3>'
const body = '<p>Fit: 5x 250mm Railgun II, Tackle: Warp Scrambler II. Bring 2 Large Shield Extender fits for the logi chain.</p>'

export default {
    title: 'Components/Data display/ComponentBlockHeader',
    component: ComponentBlockHeader,
    parameters: {
        docs: {
            description: {
                component: [
                    'A collapsible panel with a sticky header bar: the `header` slot is the clickable title, the default slot is the body. Both sit in `narrow` ComponentBlocks and the header sticks under the site header while the body scrolls.',
                    'It starts expanded. The Alpine state `global_collapse` (set by a "collapse all" control on the page) collapses it too; this needs the page-level Alpine data, so in isolation only the click works. Without a `header` slot a debug tag shows a missing-slot message.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        id: { control: 'text', description: 'Optional id for linking to the block (declared prop; not currently applied to the markup).' },
    },
    args: { slots: { header, default: body } },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: /Cormorant Navy Issue/ })).toBeVisible()
        await expect(canvas.getByText(/250mm Railgun/)).toBeVisible()
    },
}

export const CollapsesOnClick = {
    name: 'Collapses on click',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const panel = canvas.getByText(/250mm Railgun/).closest('[x-show]') as HTMLElement
        await expect(panel).toBeVisible()
        await userEvent.click(canvas.getByRole('button', { name: /Cormorant Navy Issue/ }))
        await waitFor(() => expect(panel).not.toBeVisible())
    },
}

// x-collapse measures real layout, which happy-dom does not do, so the re-expand is asserted in the browser.
export const ExpandsAgain = {
    name: 'Expands again (browser)',
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const button = canvas.getByRole('button', { name: /Cormorant Navy Issue/ })
        const panel = canvas.getByText(/250mm Railgun/).closest('[x-show]') as HTMLElement
        await userEvent.click(button)
        await waitFor(() => expect(panel).not.toBeVisible())
        await userEvent.click(button)
        await waitFor(() => expect(panel).toBeVisible())
    },
}

export const MissingHeaderSlot = {
    name: 'Missing header slot',
    args: { slots: { default: body } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        // The component renders its debug message instead of an empty button.
        await expect(canvas.getByRole('button')).toBeVisible()
        await expect(canvas.getByText(/250mm Railgun/)).toBeVisible()
    },
}

export const RichHeader = {
    name: 'Rich header',
    args: {
        slots: {
            header: '<strong>Fleet 94</strong> <small class="text-muted">38 pilots, 4 FCs</small>',
            default: '<ul><li>Round 1: Hek</li><li>Round 2: Amamake</li></ul>',
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: /Fleet 94/ })).toBeVisible()
        await expect(canvas.getByText('Round 2: Amamake')).toBeVisible()
    },
}
