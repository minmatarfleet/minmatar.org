import { expect } from 'storybook/test'
import Grid from '@components/compositions/Grid.astro'
import { space_control, demo_boxes, demo_box } from '../_controls'

const grid_of = (canvasElement: HTMLElement) => canvasElement.querySelector('.grid') as HTMLElement
const style_of = (canvasElement: HTMLElement) => grid_of(canvasElement).getAttribute('style')?.replace(/\s+/g, '') ?? ''

export default {
    title: 'Layout/Grid',
    component: Grid,
    parameters: {
        docs: {
            description: {
                component: [
                    'A responsive grid of equal columns: as many columns as fit, each at least `min_item_width`, with no media queries. Use it for card galleries (doctrines, fittings, corporations).',
                    'By default the columns are `auto-fit`, so a short last row stretches its items across the whole width. Add the `grid-fill` class to keep empty columns (`auto-fill`) so a lone item stays card-sized.',
                    'Under `min_item_width` of available width the column shrinks to 100% instead of overflowing.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        row_gap: space_control('Space between rows.'),
        column_gap: space_control('Space between columns.'),
        min_item_width: { control: 'text', description: 'Smallest column width before the grid drops a column, e.g. `10rem`.' },
        class: { control: 'text', description: 'Extra classes. `grid-fill` switches `auto-fit` to `auto-fill`.' },
    },
    args: {
        row_gap: 'var(--space-s)',
        column_gap: 'var(--space-s)',
        min_item_width: '10rem',
        slots: { default: demo_boxes(6, 'Doctrine') },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const grid = grid_of(canvasElement)
        await expect(grid).toHaveClass('grid')
        await expect(grid.children).toHaveLength(6)
        const style = style_of(canvasElement)
        await expect(style).toContain('--grid_row_gap:var(--space-s)')
        await expect(style).toContain('--grid_column_gap:var(--space-s)')
        await expect(style).toContain('--grid_min_item_width:10rem')
    },
}

export const WideColumns = {
    args: { min_item_width: '20rem', slots: { default: demo_boxes(4, 'Fleet') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--grid_min_item_width:20rem')
    },
}

export const NarrowColumns = {
    args: { min_item_width: '6rem', slots: { default: demo_boxes(12, 'Pilot') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--grid_min_item_width:6rem')
        await expect(grid_of(canvasElement).children).toHaveLength(12)
    },
}

export const Gaps = {
    args: {
        row_gap: 'var(--space-xl)',
        column_gap: 'var(--space-3xs)',
        slots: { default: demo_boxes(6, 'Corp') },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const style = style_of(canvasElement)
        await expect(style).toContain('--grid_row_gap:var(--space-xl)')
        await expect(style).toContain('--grid_column_gap:var(--space-3xs)')
    },
}

export const FitStretchesLastRow = {
    name: 'Auto-fit (last row stretches)',
    args: { slots: { default: demo_boxes(2, 'Doctrine') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(grid_of(canvasElement)).not.toHaveClass('grid-fill')
    },
}

export const Fill = {
    name: 'Auto-fill (grid-fill)',
    args: { class: 'grid-fill', slots: { default: demo_boxes(2, 'Doctrine') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(grid_of(canvasElement)).toHaveClass('grid', 'grid-fill')
    },
}

export const SingleItem = {
    args: { slots: { default: demo_box('Only one fitting') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(grid_of(canvasElement).children).toHaveLength(1)
    },
}
