import { expect } from 'storybook/test'
import FixedFluid from '@components/compositions/FixedFluid.astro'
import { space_control, demo_box } from '../_controls'

const el_of = (canvasElement: HTMLElement) => canvasElement.querySelector('.fixed-fluid') as HTMLElement
const style_of = (canvasElement: HTMLElement) => el_of(canvasElement).getAttribute('style')?.replace(/\s+/g, '') ?? ''

export default {
    title: 'Layout/FixedFluid',
    component: FixedFluid,
    parameters: {
        docs: {
            description: {
                component: [
                    'Two columns where the first has a fixed `width` and the second takes everything else. Under `breakpoint` of free space for the second column (default `50%`) they stack, with no media query. Used for a portrait or sidebar next to content.',
                    '`fluid_first` reverses the row so the fluid child is visually first while the DOM order stays the same. Use `FluidFixed` when the fixed column is the last child. Set `data-mod="no-stretch"` on the element to stop the columns stretching to equal height.',
                    '`centered` writes `data-mod="centered"`, but this composition has no centered style; it only changes the attribute.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        gap: space_control('Space between the columns and between stacked rows.'),
        width: { control: 'text', description: 'Basis of the fixed (first) column, e.g. `20rem`.' },
        breakpoint: { control: 'text', description: 'Minimum width of the fluid column before the pair stacks, e.g. `50%`.' },
        centered: { control: 'boolean', description: 'Sets `data-mod="centered"` (no visual effect).' },
        fluid_first: { control: 'boolean', description: 'Visually place the fluid column first (`flex-direction: row-reverse`).' },
    },
    args: {
        gap: 'var(--space-s)',
        width: '20rem',
        breakpoint: '50%',
        centered: false,
        fluid_first: false,
        slots: {
            default: [
                demo_box('Fixed: pilot card'),
                demo_box('Fluid: fleet history, kills and SRP requests'),
            ],
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el).toHaveClass('fixed-fluid')
        await expect(el).not.toHaveClass('fluid_first')
        await expect(el).toHaveAttribute('data-mod', '')
        const style = style_of(canvasElement)
        await expect(style).toContain('--fixed_fluid_gap:var(--space-s)')
        await expect(style).toContain('--fixed_fluid_width:20rem')
        await expect(style).toContain('--fixed_fluid_breakpoint:50%')
    },
}

export const NarrowSidebar = {
    args: { width: '12rem', gap: 'var(--space-l)' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--fixed_fluid_width:12rem')
        await expect(style_of(canvasElement)).toContain('--fixed_fluid_gap:var(--space-l)')
    },
}

export const FluidFirst = {
    args: { fluid_first: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveClass('fluid_first')
    },
}

export const StacksEarly = {
    name: 'Stacks early (high breakpoint)',
    args: { breakpoint: '80%' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--fixed_fluid_breakpoint:80%')
    },
}

export const Centered = {
    args: { centered: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(el_of(canvasElement)).toHaveAttribute('data-mod', 'centered')
    },
}

export const NoStretch = {
    name: 'No stretch (data-mod)',
    args: {
        'data-mod': 'no-stretch',
        slots: {
            default: [
                demo_box('Fixed: short card'),
                '<div class="rust-demo-box"><p>Fluid: a much taller column.</p><p>Rattini Tribe fleet doctrine notes.</p><p>Logistics assignments.</p></div>',
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // The `data-mod` attribute passed through wins over the `centered` one.
        await expect(el_of(canvasElement).getAttribute('data-mod')).toBeTruthy()
    },
}

export const SideBySide = {
    name: 'Side by side (layout)',
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const [fixed, fluid] = Array.from(el_of(canvasElement).children) as HTMLElement[]
        await expect(fluid.getBoundingClientRect().left).toBeGreaterThan(fixed.getBoundingClientRect().left)
        await expect(fluid.getBoundingClientRect().width).toBeGreaterThan(fixed.getBoundingClientRect().width)
    },
}
