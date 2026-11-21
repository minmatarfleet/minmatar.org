import { expect } from 'storybook/test'
import FluidFixed from '@components/compositions/FluidFixed.astro'
import { space_control, demo_box } from '../_controls'

const el_of = (canvasElement: HTMLElement) => canvasElement.querySelector('.fluid-fixed') as HTMLElement
const style_of = (canvasElement: HTMLElement) => el_of(canvasElement).getAttribute('style')?.replace(/\s+/g, '') ?? ''

export default {
    title: 'Layout/FluidFixed',
    component: FluidFixed,
    parameters: {
        docs: {
            description: {
                component: [
                    'Two columns where the last has a fixed `width` and the first takes everything else, e.g. content with an action panel or stat card on the right. Under `breakpoint` of free space for the first column (default `50%`) they stack.',
                    'The mirror of `FixedFluid` (fixed child first). Set `data-mod="no-stretch"` to stop the columns stretching to equal height.',
                    '`centered` writes `data-mod="centered"`, but this composition has no centered style; it only changes the attribute.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        gap: space_control('Space between the columns and between stacked rows.'),
        width: { control: 'text', description: 'Basis of the fixed (last) column, e.g. `20rem`.' },
        breakpoint: { control: 'text', description: 'Minimum width of the fluid column before the pair stacks, e.g. `50%`.' },
        centered: { control: 'boolean', description: 'Sets `data-mod="centered"` (no visual effect).' },
    },
    args: {
        gap: 'var(--space-s)',
        width: '20rem',
        breakpoint: '50%',
        centered: false,
        slots: {
            default: [
                demo_box('Fluid: fleet description and doctrine fits'),
                demo_box('Fixed: sign-up panel'),
            ],
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = el_of(canvasElement)
        await expect(el).toHaveClass('fluid-fixed')
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

export const WideSidebar = {
    args: { width: '30rem' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(style_of(canvasElement)).toContain('--fixed_fluid_width:30rem')
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

export const SideBySide = {
    name: 'Side by side (layout)',
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const [fluid, fixed] = Array.from(el_of(canvasElement).children) as HTMLElement[]
        await expect(fixed.getBoundingClientRect().left).toBeGreaterThan(fluid.getBoundingClientRect().left)
        await expect(fluid.getBoundingClientRect().width).toBeGreaterThan(fixed.getBoundingClientRect().width)
    },
}
