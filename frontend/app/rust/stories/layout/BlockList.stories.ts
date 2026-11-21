import { expect } from 'storybook/test'
import BlockList from '@components/compositions/BlockList.astro'
import { space_control, demo_boxes } from '../_controls'

const el_of = (canvasElement: HTMLElement) => canvasElement.querySelector('.block-list') as HTMLElement
const style_of = (canvasElement: HTMLElement) => el_of(canvasElement).getAttribute('style')?.replace(/\s+/g, '') ?? ''

export default {
    title: 'Layout/BlockList',
    component: BlockList,
    parameters: {
        docs: {
            description: {
                component: [
                    'A vertical list where every child is full width and rows are separated by `gap` (flexbox `gap`, so it also works for the first and last child).',
                    'Reach for it for rows of cards or list entries. Use `Flexblock` when children should keep their natural width or you need `centered` / `push-bottom`; set `data-mod="centered"` here to center children instead of stretching text.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        gap: space_control('Space between rows.'),
    },
    args: {
        gap: 'var(--space-s)',
        slots: { default: demo_boxes(4, 'SRP request') },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el).toHaveClass('block-list')
        await expect(el.children).toHaveLength(4)
        await expect(style_of(canvasElement)).toContain('--block_list_gap:var(--space-s)')
    },
}

export const Gaps = {
    args: { gap: 'var(--space-xl)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--block_list_gap:var(--space-xl)')
    },
}

export const Tight = {
    args: { gap: 'var(--space-3xs)', slots: { default: demo_boxes(6, 'Pilot') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--block_list_gap:var(--space-3xs)')
        await expect(el_of(canvasElement).children).toHaveLength(6)
    },
}

export const FluidGap = {
    name: 'Fluid gap token',
    args: { gap: 'var(--space-m-l)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--block_list_gap:var(--space-m-l)')
    },
}

export const Centered = {
    args: {
        'data-mod': 'centered',
        slots: { default: ['<p>Doctrine approved</p>', '<p>Fits checked</p>', '<p>Ready to undock</p>'] },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveAttribute('data-mod', 'centered')
    },
}

export const FullWidthChildren = {
    name: 'Children are full width',
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        for (const child of Array.from(el.children) as HTMLElement[]) {
            await expect(Math.round(child.getBoundingClientRect().width)).toBe(Math.round(el.getBoundingClientRect().width))
        }
    },
}
