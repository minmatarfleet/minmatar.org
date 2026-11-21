import { expect, within } from 'storybook/test'
import Center from '@components/compositions/Center.astro'
import Button from '@components/blocks/Button.astro'
import { demo_box } from '../_controls'

export default {
    title: 'Layout/Center',
    component: Center,
    parameters: {
        docs: {
            description: {
                component: [
                    'Centers its content on both axes with flexbox. It has no props of its own: every attribute is passed straight to the `<div>`, so give it a size (`style`, `class`, `id`) for the centering to be visible.',
                    'Use it for empty placeholders, icons in a fixed box or a spinner in a panel. For page-width centering use `Wrapper` with `centered`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        class: { control: 'text', description: 'Passed through to the `<div>`; use it to size the box.' },
        style: { control: 'text', description: 'Passed through to the `<div>`; give the box a size.' },
    },
    args: {
        style: 'min-block-size: 10rem',
        slots: { default: demo_box('Centered content') },
    },
}

const root_of = (canvasElement: HTMLElement) => canvasElement.firstElementChild as HTMLElement

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Centered content')).toBeVisible()
        await expect(root_of(canvasElement).tagName).toBe('DIV')
        await expect(root_of(canvasElement).getAttribute('style')).toContain('min-block-size')
    },
}

export const Text = {
    args: { slots: { default: '<p>No pilots are on the roster yet.</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('No pilots are on the roster yet.')).toBeVisible()
    },
}

export const WithButton = {
    args: {
        slots: {
            default: { component: Button, props: { href: '/fleets/' }, slots: { default: 'Find a fleet' } },
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('link', { name: 'Find a fleet' })).toHaveAttribute('href', '/fleets/')
    },
}

export const PassesAttributes = {
    name: 'Passes attributes through',
    args: { id: 'empty-roster', class: 'rust-center-demo', 'aria-label': 'Empty roster', role: 'region' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const region = within(canvasElement).getByRole('region', { name: 'Empty roster' })
        await expect(region).toHaveAttribute('id', 'empty-roster')
        await expect(region).toHaveClass('rust-center-demo')
    },
}

export const CentersBothAxes = {
    name: 'Centers on both axes',
    args: { slots: { default: '<span id="centered-dot">Dot</span>' } },
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const box = root_of(canvasElement).getBoundingClientRect()
        const dot = canvasElement.querySelector('#centered-dot')!.getBoundingClientRect()
        await expect(Math.abs((dot.left + dot.width / 2) - (box.left + box.width / 2))).toBeLessThan(2)
        await expect(Math.abs((dot.top + dot.height / 2) - (box.top + box.height / 2))).toBeLessThan(2)
    },
}
