import { expect, within } from 'storybook/test'
import TextBox from '@components/layout/TextBox.astro'

export default {
    title: 'Page/TextBox',
    component: TextBox,
    parameters: {
        docs: {
            description: {
                component: [
                    'A `Wrapper` capped at `--max-text-width` with no padding, so running text keeps a readable line length inside a wider page. Stack several for the paragraphs of a content page.',
                    'Override `max_width` for narrower copy. For full-width panels use `Wrapper` or `ComponentBlock` instead. Extra attributes pass through to the wrapper.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        max_width: { control: 'text', description: 'Maximum width; a token such as `var(--max-text-width)` or a length.' },
    },
    args: {
        max_width: 'var(--max-text-width)',
        slots: {
            default: '<p>The Minmatar Fleet Alliance flies together in fleets that anyone can join. Check the doctrine, undock with the fleet and file SRP afterwards for covered losses.</p>',
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const wrapper = canvasElement.querySelector('.wrapper') as HTMLElement
        await expect(wrapper).not.toBeNull()
        await expect(wrapper.getAttribute('style')).toContain('var(--max-text-width)')
        await expect(within(canvasElement).getByText(/undock with the fleet/)).toBeVisible()
    },
}

export const Narrow = {
    args: { max_width: '30rem' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const wrapper = canvasElement.querySelector('.wrapper') as HTMLElement
        await expect(wrapper.getAttribute('style')).toContain('30rem')
    },
}

export const NoPadding = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const style = (canvasElement.querySelector('.wrapper') as HTMLElement).getAttribute('style') ?? ''
        await expect(style).toMatch(/--wrapper_padding_inline:\s*0/)
        await expect(style).toMatch(/--wrapper_padding_block:\s*0/)
    },
}

export const Paragraphs = {
    args: {
        slots: {
            default: [
                '<h2>Joining a fleet</h2>',
                '<p>Open the fleet page, check that your ship matches a doctrine fit and press Join. The fleet commander will send an invite in game.</p>',
                '<p>If you lose a doctrine ship in a covered fleet, file an SRP request from the fleet page within 30 days of the fight.</p>',
            ].join(''),
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Joining a fleet' })).toBeVisible()
        await expect(canvasElement.querySelectorAll('p').length).toBe(2)
    },
}

export const WithAttributes = {
    args: { id: 'about-text', class: 'text-muted' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('#about-text')).toHaveClass('wrapper')
    },
}
