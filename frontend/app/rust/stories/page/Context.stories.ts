import { expect, within } from 'storybook/test'
import Context from '@components/layout/Context.astro'
import Badge from '@components/blocks/Badge.astro'
import { demo_boxes } from '../_controls'

export default {
    title: 'Page/Context',
    component: Context,
    parameters: {
        docs: {
            description: {
                component: [
                    'A full-width vertical stack with a tight `--space-3xs` gap, used to group a heading with the line that explains it (a title and its sub-label, a value and its caption).',
                    'It is a thin `Flexblock`: pass `gap` to loosen it, or use `Flexblock` directly when you need other options. Extra attributes pass through.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        gap: { control: 'text', description: 'Space between children; defaults to `var(--space-3xs)`.' },
    },
    args: {
        slots: {
            default: '<strong>Rifter Armada</strong><small class="text-muted">Alliance doctrine, 30 pilots</small>',
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Rifter Armada')).toBeVisible()
        await expect(canvas.getByText(/30 pilots/)).toBeVisible()
        const root = canvasElement.firstElementChild as HTMLElement
        await expect(root).toHaveClass('w-full')
    },
}

export const GapBetween = {
    args: { gap: 'var(--space-l)', slots: { default: demo_boxes(3, 'Section') } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const root = canvasElement.firstElementChild as HTMLElement
        await expect(root.getAttribute('style')).toContain('var(--space-l)')
        await expect(canvasElement.querySelectorAll('.rust-demo-box')).toHaveLength(3)
    },
}

export const TightByDefault = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const root = canvasElement.firstElementChild as HTMLElement
        await expect(root.getAttribute('style')).toContain('var(--space-3xs)')
    },
}

export const WithBadges = {
    args: {
        slots: {
            default: [
                '<h3>Amamake freeport defence</h3>',
                { component: Badge, props: { color: 'fleet-red' }, slots: { default: 'Strategic' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Amamake freeport defence' })).toBeVisible()
        await expect(canvas.getByText('Strategic')).toBeVisible()
    },
}

export const WithAttributes = {
    args: { id: 'fleet-context', 'data-fleet-id': '92221' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const root = canvasElement.querySelector('#fleet-context')
        await expect(root).toHaveAttribute('data-fleet-id', '92221')
    },
}
