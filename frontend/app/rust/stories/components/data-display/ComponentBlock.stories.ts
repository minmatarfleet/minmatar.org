import { expect, within } from 'storybook/test'
import ComponentBlock from '@components/blocks/ComponentBlock.astro'
import { select_control } from '../../_controls'

const body = '<h3>Fleet 94 debrief</h3><p>38 pilots flew the Cormorant Navy Issue doctrine through three rounds.</p>'

export default {
    title: 'Components/Data display/ComponentBlock',
    component: ComponentBlock,
    parameters: {
        docs: {
            description: {
                component: [
                    'The standard bordered panel: a translucent card with the site\'s block padding. Wrap page sections in it instead of hand-rolling a border and background.',
                    '`width` caps the panel (`narrow` is the readable text width, `thin` is 650px, `normal` fills its parent). `heavier` swaps in the denser transparency class. `Card` is only the picture card with hover actions; do not use it for panels.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        padding_block: { control: 'text', description: 'Block padding; defaults to the `--component-padding-block` token.' },
        padding_inline: { control: 'text', description: 'Inline padding; defaults to `--space-l-xl`.' },
        width: select_control(['narrow', 'normal', 'thin'], 'Maximum width of the panel.'),
        heavier: { control: 'boolean', description: 'Use the heavier transparency effect (more opaque background).' },
    },
    args: {
        padding_block: 'var(--component-padding-block)',
        padding_inline: 'var(--space-l-xl)',
        width: 'normal',
        heavier: false,
        slots: { default: body },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const block = canvasElement.querySelector('.component') as HTMLElement
        await expect(block).toBeTruthy()
        await expect(block).toHaveClass('card', 'border', 'light-transparency')
        await expect(block).not.toHaveClass('light-transparency-heavier')
        await expect(within(block).getByRole('heading', { name: 'Fleet 94 debrief' })).toBeVisible()
    },
}

export const Heavier = {
    args: { heavier: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const block = canvasElement.querySelector('.component') as HTMLElement
        await expect(block).toHaveClass('light-transparency-heavier')
    },
}

export const Narrow = {
    args: { width: 'narrow' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const block = canvasElement.querySelector('.component') as HTMLElement
        await expect(block.getAttribute('style')).toContain('var(--max-text-width)')
    },
}

export const Thin = {
    args: { width: 'thin', slots: { default: '<p>Pilots on the SRP queue: 12</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const block = canvasElement.querySelector('.component') as HTMLElement
        await expect(block.getAttribute('style')).toContain('650px')
        await expect(within(block).getByText('Pilots on the SRP queue: 12')).toBeVisible()
    },
}

export const CustomPadding = {
    args: { padding_block: 'var(--space-s)', padding_inline: 'var(--space-s)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const style = (canvasElement.querySelector('.component') as HTMLElement).getAttribute('style') ?? ''
        await expect(style).toContain('var(--space-s)')
    },
}

export const PassthroughAttributes = {
    name: 'Passthrough attributes',
    args: { id: 'fleet-notes', 'data-testid': 'notes', slots: { default: '<p>Notes for the FC</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const block = within(canvasElement).getByTestId('notes')
        await expect(block).toHaveAttribute('id', 'fleet-notes')
        await expect(block).toHaveClass('component')
    },
}
