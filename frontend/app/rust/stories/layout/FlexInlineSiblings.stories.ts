import { expect } from 'storybook/test'
import FlexInlineSiblings from '@components/compositions/FlexInlineSiblings.astro'
import Button from '@components/blocks/Button.astro'
import { space_control, radio_control } from '../_controls'

const el_of = (canvasElement: HTMLElement) => canvasElement.querySelector('.flex-inline-siblings') as HTMLElement
const style_of = (canvasElement: HTMLElement) => el_of(canvasElement).getAttribute('style')?.replace(/\s+/g, '') ?? ''

export default {
    title: 'Layout/FlexInlineSiblings',
    component: FlexInlineSiblings,
    parameters: {
        docs: {
            description: {
                component: [
                    'Exactly two siblings in a row where one may shrink and the other keeps its natural size, e.g. a paragraph next to a button. When there is no room the two wrap onto separate lines instead of squashing.',
                    '`shrinkable-sibbling` picks which child (`first` or `second`) takes the leftover space; `min-shink-width` is the width that child keeps before the pair wraps. The prop names are spelled as in the component (`sibbling`, `shink`) and are hyphenated, so pass them with quotes.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        gap: space_control('Space between the two siblings.'),
        'min-shink-width': { control: 'text', description: 'Width the shrinkable child keeps before the pair wraps, e.g. `250px`.' },
        'shrinkable-sibbling': radio_control(['first', 'second'] as const, 'Which child flexes; the other stays at its natural width.'),
    },
    args: {
        gap: 'var(--space-s)',
        'min-shink-width': '250px',
        'shrinkable-sibbling': 'first',
        slots: {
            default: [
                '<p>Browse the alliance brand kit: logos, colors and the approved way to talk about Minmatar Fleet in public.</p>',
                { component: Button, props: { size: 'sm', href: '/brand/' }, slots: { default: 'Browse' } },
            ],
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el).toHaveClass('flex-inline-siblings', 'shrink-first')
        await expect(el.children).toHaveLength(2)
        await expect(style_of(canvasElement)).toContain('--flex_inline_siblings_gap:var(--space-s)')
        await expect(style_of(canvasElement)).toContain('--flex_inline_siblings_min_shink_width:250px')
    },
}

export const ShrinkSecond = {
    args: {
        'shrinkable-sibbling': 'second',
        slots: {
            default: [
                { component: Button, props: { size: 'sm', href: '/fleets/' }, slots: { default: 'Upcoming fleets' } },
                '<p>Fleets are posted by FCs at least a day ahead; check the schedule for your timezone.</p>',
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveClass('shrink-second')
        await expect(el_of(canvasElement)).not.toHaveClass('shrink-first')
    },
}

export const WideMinimum = {
    name: 'Wraps early (large min width)',
    args: { 'min-shink-width': '40rem' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--flex_inline_siblings_min_shink_width:40rem')
    },
}

export const BigGap = {
    args: { gap: 'var(--space-xl)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--flex_inline_siblings_gap:var(--space-xl)')
    },
}

export const ShrinkableTakesLeftover = {
    name: 'Shrinkable child takes the leftover space',
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        const first = el.firstElementChild as HTMLElement
        const last = el.lastElementChild as HTMLElement
        await expect(getComputedStyle(first).flexGrow).toBe('1')
        await expect(getComputedStyle(last).flexGrow).toBe('0')
    },
}
