import { expect } from 'storybook/test'
import ThemeModes from '../../components/foundations/ThemeModes.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Foundations/Themes',
    component: ThemeModes,
    parameters: {
        docs: {
            description: {
                component: [
                    'The site is dark only (`color-scheme: dark`). Two modes change it, both switched by the accessibility options on `<body>`: **colour-blind mode** (`body.color-blind-mode`) redefines `--fleet-red`, `--green` and `--button-color`, and **UI scaling** (`body.ui-scaling-80/90/120`) zooms the page.',
                    'Never pick a colour-blind-safe colour by hand: use the tokens and the mode does the rest. Use the **Theme** and **UI scale** buttons in the toolbar to preview any story in each mode.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        mode: { control: 'inline-radio', options: ['side-by-side', 'scales'], description: 'Colour modes side by side, or the UI scales.' },
    },
    args: { mode: 'side-by-side' },
}

export const ColourModes = {
    name: 'Colour modes',
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('[data-theme="default"]')).not.toBeNull()
        const blind = canvasElement.querySelector<HTMLElement>('[data-theme="body.color-blind-mode"]')!
        await expect(blind).toHaveClass('color-blind-mode')
        for (const name of ['--fleet-red', '--green', '--button-color'])
            await expect(blind.querySelector('.redefines')!.textContent).toContain(name)
    },
}

export const UiScales = {
    name: 'UI scales',
    args: { mode: 'scales' },
    play: async ({ canvasElement }: Ctx) => {
        const scales = [...canvasElement.querySelectorAll<HTMLElement>('[data-scale]')].map((el) => Number(el.dataset.scale))
        await expect(scales).toEqual([80, 90, 100, 120])
        await expect(canvasElement.querySelector('[data-scale="120"]')).toHaveClass('ui-scaling-120')
    },
}

export const ComparedSwatches = {
    name: 'Same tokens, both modes',
    play: async ({ canvasElement }: Ctx) => {
        const themes = canvasElement.querySelectorAll('[data-theme]')
        for (const theme of themes)
            await expect(theme.querySelectorAll('[data-token]').length).toBe(5)
    },
}
