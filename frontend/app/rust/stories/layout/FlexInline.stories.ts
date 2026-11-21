import { expect } from 'storybook/test'
import FlexInline from '@components/compositions/FlexInline.astro'
import { space_control, select_control, JUSTIFY, demo_boxes } from '../_controls'

const el_of = (canvasElement: HTMLElement) => canvasElement.querySelector('.flex-inline') as HTMLElement
const style_of = (canvasElement: HTMLElement) => el_of(canvasElement).getAttribute('style')?.replace(/\s+/g, '') ?? ''

export default {
    title: 'Layout/FlexInline',
    component: FlexInline,
    parameters: {
        docs: {
            description: {
                component: [
                    'A horizontal row that wraps onto the next line when it runs out of room: tags, buttons, badges and metadata. Items are vertically centered.',
                    'Use `justification` to push the row to the end or spread it out. If one item should shrink before the row wraps (a title next to a button), use `FlexInlineSiblings` instead.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        gap: space_control('Space between items, horizontally and when wrapped.'),
        justification: select_control(JUSTIFY, 'Main-axis alignment (`justify-content`).'),
    },
    args: {
        gap: 'var(--space-s)',
        justification: 'flex-start',
        slots: { default: demo_boxes(4, 'Tag') },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el).toHaveClass('flex-inline')
        await expect(el.children).toHaveLength(4)
        await expect(style_of(canvasElement)).toContain('--flex_inline_gap:var(--space-s)')
        await expect(style_of(canvasElement)).toContain('--flex_inline_justification:flex-start')
    },
}

export const Gaps = {
    args: { gap: 'var(--space-xl)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--flex_inline_gap:var(--space-xl)')
    },
}

export const TightGap = {
    args: { gap: 'var(--space-3xs)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--flex_inline_gap:var(--space-3xs)')
    },
}

export const Centered = {
    args: { justification: 'center' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--flex_inline_justification:center')
    },
}

export const EndAligned = {
    args: { justification: 'flex-end', slots: { default: demo_boxes(2, 'Action') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--flex_inline_justification:flex-end')
    },
}

export const SpaceBetween = {
    args: { justification: 'space-between', slots: { default: demo_boxes(3, 'Stat') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--flex_inline_justification:space-between')
    },
}

export const Wrapping = {
    name: 'Wraps when crowded',
    args: { slots: { default: demo_boxes(24, 'Pilot') } },
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(getComputedStyle(el).flexWrap).toBe('wrap')
        const tops = new Set(Array.from(el.children).map((c) => (c as HTMLElement).offsetTop))
        await expect(tops.size).toBeGreaterThan(1)
    },
}
