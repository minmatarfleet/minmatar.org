import { expect, within } from 'storybook/test'
import DamageTypeIcon from '@components/blocks/role-guide/DamageTypeIcon.astro'

type Ctx = { canvasElement: HTMLElement }

const TYPES = ['em', 'thermal', 'kinetic', 'explosive']

export default {
    title: 'Foundations/Icons/DamageTypeIcon',
    component: DamageTypeIcon,
    parameters: {
        docs: {
            description: {
                component: 'One EVE damage type as a small coloured glyph, labelled for screen readers. CCP does not serve damage-type icons through the Image Server and the third-party rules forbid client art, so these are our own glyphs (`src/helpers/damage_types.ts`): EM a bolt, thermal a flame, kinetic a shell, explosive a burst. Used by the role guides and fit summaries.',
            },
        },
    },
    argTypes: {
        type: { control: 'inline-radio', options: TYPES, description: 'The damage type.' },
        labelled: { control: 'boolean', description: 'Show the type\'s name next to the glyph.' },
    },
    args: { type: 'em', labelled: false },
}

const has_glyph = async (canvas: HTMLElement) => {
    await expect(canvas.querySelector('svg')).not.toBeNull()
}

export const Em = {
    name: 'EM',
    play: async ({ canvasElement }: Ctx) => {
        await has_glyph(canvasElement)
        // Unlabelled, the glyph itself is the image and carries the name.
        const svg = canvasElement.querySelector('svg')!
        await expect(svg).toHaveAttribute('role', 'img')
        await expect(svg.getAttribute('aria-label')).toBeTruthy()
    },
}

export const Thermal = { args: { type: 'thermal' }, play: async ({ canvasElement }: Ctx) => has_glyph(canvasElement) }
export const Kinetic = { args: { type: 'kinetic' }, play: async ({ canvasElement }: Ctx) => has_glyph(canvasElement) }
export const Explosive = { args: { type: 'explosive' }, play: async ({ canvasElement }: Ctx) => has_glyph(canvasElement) }

export const Labelled = {
    args: { type: 'thermal', labelled: true },
    play: async ({ canvasElement }: Ctx) => {
        await has_glyph(canvasElement)
        // Labelled, the text is the name and the glyph is hidden from screen readers.
        await expect(canvasElement.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
        await expect(within(canvasElement).getByText(/thermal/i)).toBeTruthy()
    },
}
