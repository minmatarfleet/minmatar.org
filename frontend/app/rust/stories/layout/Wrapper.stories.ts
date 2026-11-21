import { expect, within } from 'storybook/test'
import Wrapper from '@components/compositions/Wrapper.astro'
import { space_control, demo_box } from '../_controls'

const style_of = (canvasElement: HTMLElement) =>
    canvasElement.querySelector('.wrapper')!.getAttribute('style')?.replace(/\s+/g, '') ?? ''

export default {
    title: 'Layout/Wrapper',
    component: Wrapper,
    parameters: {
        docs: {
            description: {
                component: [
                    'The page-width container: pads the content on the inline and block axes and caps it at `max_width`. Almost every page section sits in one.',
                    'It is left-aligned unless `centered` is set. `neocom` adds the width of the side navigation to the inline-start padding (and drops back to a small gutter under 890px), so use it on full-bleed pages that sit next to the Neocom rail.',
                    'All values are set through CSS custom properties (`--wrapper_*`), so pass tokens such as `var(--space-xl)`, never raw lengths.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        padding_inline: space_control('Inline (left/right) padding, a space token.'),
        padding_block: space_control('Block (top/bottom) padding, a space token.'),
        max_width: { control: 'text', description: 'Maximum inline size, e.g. `80rem` or `40rem`.' },
        centered: { control: 'boolean', description: 'Centers the wrapper horizontally (`data-mod="centered"`).' },
        neocom: { control: 'boolean', description: 'Adds the Neocom rail width to the inline-start padding.' },
    },
    args: {
        padding_inline: 'var(--space-2xl-3xl)',
        padding_block: 'var(--space-2xl)',
        max_width: '80rem',
        centered: false,
        neocom: false,
        slots: { default: demo_box('Fleet schedule section') },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const wrapper = canvasElement.querySelector('.wrapper')!
        await expect(within(canvasElement).getByText('Fleet schedule section')).toBeVisible()
        await expect(wrapper).not.toHaveClass('compensate-neocom')
        await expect(wrapper).toHaveAttribute('data-mod', '')
        const style = style_of(canvasElement)
        await expect(style).toContain('--wrapper_padding_inline:var(--space-2xl-3xl)')
        await expect(style).toContain('--wrapper_padding_block:var(--space-2xl)')
        await expect(style).toContain('--wrapper_max_width:80rem')
    },
}

export const Centered = {
    args: {
        centered: true,
        max_width: '40rem',
        slots: { default: demo_box('Narrow, centered article column') },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const wrapper = canvasElement.querySelector('.wrapper')!
        await expect(wrapper).toHaveAttribute('data-mod', 'centered')
        await expect(style_of(canvasElement)).toContain('--wrapper_max_width:40rem')
    },
}

export const Compact = {
    args: {
        padding_inline: 'var(--space-s)',
        padding_block: 'var(--space-xs)',
        slots: { default: demo_box('Tight padding for a dense panel') },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const style = style_of(canvasElement)
        await expect(style).toContain('--wrapper_padding_inline:var(--space-s)')
        await expect(style).toContain('--wrapper_padding_block:var(--space-xs)')
    },
}

export const Roomy = {
    args: {
        padding_inline: 'var(--space-3xl)',
        padding_block: 'var(--space-3xl)',
        slots: { default: demo_box('Generous padding for a landing section') },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const style = style_of(canvasElement)
        await expect(style).toContain('--wrapper_padding_inline:var(--space-3xl)')
        await expect(style).toContain('--wrapper_padding_block:var(--space-3xl)')
    },
}

export const BesideNeocom = {
    name: 'Beside the Neocom (neocom)',
    args: {
        neocom: true,
        slots: { default: demo_box('Content starts after the Neocom rail') },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.wrapper')).toHaveClass('compensate-neocom')
    },
}

export const Nested = {
    args: {
        slots: {
            default: [
                demo_box('Outer wrapper'),
                { component: Wrapper, props: { padding_inline: 'var(--space-s)', padding_block: 'var(--space-s)' }, slots: { default: demo_box('Inner wrapper') } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const wrappers = canvasElement.querySelectorAll('.wrapper')
        await expect(wrappers).toHaveLength(2)
        await expect(wrappers[1].getAttribute('style')?.replace(/\s+/g, '')).toContain('--wrapper_padding_inline:var(--space-s)')
    },
}
