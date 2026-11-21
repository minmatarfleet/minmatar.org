import { expect, userEvent } from 'storybook/test'
import MotionLayers from '../../components/foundations/MotionLayers.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Foundations/Motion, layers and glass',
    component: MotionLayers,
    parameters: {
        docs: {
            description: {
                component: [
                    'Transitions (`--fast-transition` for hovers and presses, `--normal-transition` for panels and menus), the z-index chain, and the glass (transparency) classes.',
                    'Z-index is one additive chain from `--base-z-index`: header → neocom → backdrop → dialog → page finder → alert → dialog close → tooltips. Never invent a value. Hover scale effects go inside `@media (hover: hover)`; press effects inside `@media (hover: none)`.',
                    'Glass classes render solid on phones and blur from 980 px; prefer them to a hand-rolled `rgba()` and `backdrop-filter`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        section: { control: 'inline-radio', options: ['all', 'motion', 'layers', 'effects'], description: 'Which section to show.' },
    },
    args: { section: 'all' },
}

export const All = {
    play: async ({ canvasElement }: Ctx) => {
        for (const section of ['motion', 'layers', 'effects'])
            await expect(canvasElement.querySelector(`[data-section="${section}"]`)).not.toBeNull()
    },
}

export const Motion = {
    args: { section: 'motion' },
    play: async ({ canvasElement }: Ctx) => {
        const rows = [...canvasElement.querySelectorAll<HTMLElement>('[data-token]')]
        await expect(rows.map((r) => r.dataset.token)).toEqual(['--fast-transition', '--normal-transition', '--slow-transition', '--slowest-transition'])
        await userEvent.hover(rows[0])
        await expect(rows[0].getAttribute('style')).toContain('var(--fast-transition)')
    },
}

export const Layers = {
    args: { section: 'layers' },
    play: async ({ canvasElement }: Ctx) => {
        const names = [...canvasElement.querySelectorAll<HTMLElement>('[data-token]')].map((r) => r.dataset.token)
        for (const name of ['--base-z-index', '--header-z-index', '--dialog-z-index', '--tooltips-z-index'])
            await expect(names).toContain(name)
    },
}

export const Glass = {
    args: { section: 'effects' },
    play: async ({ canvasElement }: Ctx) => {
        const effects = [...canvasElement.querySelectorAll<HTMLElement>('[data-effect]')]
        await expect(effects.length).toBe(6)
        for (const el of effects)
            await expect(el).toHaveClass(el.dataset.effect!)
    },
}
