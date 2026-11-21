import { expect } from 'storybook/test'
import SpaceScale from '../../components/foundations/SpaceScale.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Foundations/Spacing and layout',
    component: SpaceScale,
    parameters: {
        docs: {
            description: {
                component: 'The fluid space scale (Utopia) and the layout widths. Use single steps (`--space-s`) for fixed rhythm and one-up pairs (`--space-s-m`, `--space-l-xl`) for gaps that open up on wide screens. Never write `px` or `rem` for spacing. Each bar is drawn with its token.',
            },
        },
    },
    argTypes: {
        show_layout: { control: 'boolean', description: 'Also list the layout widths (`--max-text-width`, `--neocom-width`, ...).' },
    },
    args: { show_layout: true },
}

export const Scale = {
    name: 'Space scale',
    play: async ({ canvasElement }: Ctx) => {
        const names = [...canvasElement.querySelectorAll<HTMLElement>('[data-token^="--space-"]')].map((el) => el.dataset.token)
        for (const name of ['--space-3xs', '--space-s', '--space-3xl', '--space-s-m', '--space-2xl-3xl', '--space-s-l'])
            await expect(names).toContain(name)
    },
}

export const Bars = {
    name: 'Bars use their token',
    args: { show_layout: false },
    play: async ({ canvasElement }: Ctx) => {
        for (const row of canvasElement.querySelectorAll<HTMLElement>('[data-token]'))
            await expect(row.querySelector('.bar')!.getAttribute('style')).toContain(`var(${row.dataset.token})`)
    },
}

export const Layout = {
    name: 'Layout widths',
    play: async ({ canvasElement }: Ctx) => {
        for (const name of ['--max-content-width', '--max-text-width', '--neocom-width', '--sticky-top'])
            await expect(canvasElement.querySelector(`[data-token="${name}"]`)).not.toBeNull()
    },
}
