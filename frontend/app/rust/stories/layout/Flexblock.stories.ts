import { expect } from 'storybook/test'
import Flexblock from '@components/compositions/Flexblock.astro'
import { space_control, demo_boxes } from '../_controls'

const el_of = (canvasElement: HTMLElement) => canvasElement.querySelector('.flex-block') as HTMLElement

export default {
    title: 'Layout/Flexblock',
    component: Flexblock,
    parameters: {
        docs: {
            description: {
                component: [
                    'A vertical stack: children flow in a column and each gets a top margin from `gap`. The default way to space a heading, text and controls inside a panel.',
                    'The first child never gets a margin, unless `first_element_gap` is set (it then shifts the whole stack up by the gap). `centered` centers children horizontally. Give a child the `push-bottom` class to pin it and everything after it to the bottom of a tall stack.',
                    'Only the space tokens in `SPACES` (plus `0`) have a matching `gap-*` class; any other value produces no spacing.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        gap: space_control('Space between children, applied as `margin-block-start` via a `gap-<token>` class.'),
        centered: { control: 'boolean', description: 'Center children on the cross axis (`data-mod="centered"`).' },
        first_element_gap: { control: 'boolean', description: 'Also give the first child its gap (the stack is pulled up by the same amount).' },
    },
    args: {
        gap: 'var(--space-s)',
        centered: false,
        first_element_gap: false,
        slots: { default: demo_boxes(3, 'Section') },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el).toHaveClass('flex-block', 'gap---space-s')
        await expect(el).toHaveAttribute('data-mod', '')
        await expect(el.children).toHaveLength(3)
    },
}

export const Gaps = {
    args: { gap: 'var(--space-xl)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveClass('gap---space-xl')
    },
}

export const NoGap = {
    args: { gap: '0' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveClass('gap-0')
    },
}

export const FluidGap = {
    name: 'Fluid gap token',
    args: { gap: 'var(--space-s-m)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveClass('gap---space-s-m')
    },
}

export const ComponentBlockGap = {
    args: { gap: 'var(--component-block-gap)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveClass('gap---component-block-gap')
    },
}

export const Centered = {
    args: {
        centered: true,
        slots: {
            default: [
                '<h3>Fleet standing orders</h3>',
                '<p>Form up on the FC and wait for the doctrine ping.</p>',
                '<div class="rust-demo-box">Ready check</div>',
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveAttribute('data-mod', 'centered')
        await expect(el_of(canvasElement).children).toHaveLength(3)
    },
}

export const FirstElementGap = {
    args: { first_element_gap: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveClass('first_element_gap')
    },
}

export const PushBottom = {
    name: 'Pinned footer (push-bottom)',
    args: {
        class: 'min-h-80',
        slots: {
            default: [
                '<h3>Doctrine: Muninn fleet</h3>',
                '<p>30 pilots, 2 logi, 1 FC.</p>',
                '<div class="rust-demo-box push-bottom">Pinned to the bottom</div>',
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement).querySelector('.push-bottom')).not.toBeNull()
    },
}
