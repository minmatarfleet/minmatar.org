import { expect, within } from 'storybook/test'
import ColorTokens from '../../components/foundations/ColorTokens.astro'

const FAMILIES = ['Brand palette', 'Semantic', 'Alpha tints', 'Colour-blind mode', 'Glass (effects)', 'Item meta groups', 'Security status', 'Discord']

type Ctx = { canvasElement: HTMLElement }

const tokens = (canvas: HTMLElement) => [...canvas.querySelectorAll<HTMLElement>('[data-token]')]

export default {
    title: 'Foundations/Colors',
    component: ColorTokens,
    parameters: {
        docs: {
            description: {
                component: [
                    'Every colour token in `src/styles/properties/`, read from the stylesheets when the page renders and drawn with the token itself, so this page cannot fall behind the CSS.',
                    '**Primitive** tokens hold a raw value (`--fleet-red: #b53620`); **semantic** tokens alias one for a purpose (`--foreground: var(--fleet-yellow)`). Components use semantic tokens where one exists. *Themed* marks a token that `body.color-blind-mode` redefines.',
                    'For any other alpha, mix a token: `color-mix(in srgb, var(--highlight) 20%, transparent)`. Hand-written hex colours are listed under **Colours not yet tokens**.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        family: { control: 'select', options: [undefined, ...FAMILIES], description: 'Show one family; all when unset.' },
        show_values: { control: 'boolean', description: 'Show each token\'s declared value.' },
    },
    args: { show_values: true },
}

export const AllColors = {
    name: 'All colours',
    play: async ({ canvasElement }: Ctx) => {
        const root = canvasElement.querySelector<HTMLElement>('.color-tokens')!
        const all = tokens(canvasElement)
        await expect(all.length).toBe(Number(root.dataset.total))
        await expect(all.length).toBeGreaterThan(50)
        for (const family of ['Brand palette', 'Semantic', 'Security status'])
            await expect(canvasElement.querySelector(`[data-family="${family}"]`)).not.toBeNull()
        // Every swatch is drawn with its own token.
        for (const item of all)
            await expect(item.querySelector('.swatch')!.getAttribute('style')).toContain(`var(${item.dataset.token})`)
    },
}

export const Brand = {
    args: { family: 'Brand palette' },
    play: async ({ canvasElement }: Ctx) => {
        for (const name of ['--fleet-yellow', '--fleet-red', '--alliance-blue', '--militia-purple', '--green'])
            await expect(canvasElement.querySelector(`[data-token="${name}"]`)).not.toBeNull()
        await expect(within(canvasElement).getByText('#b53620')).toBeTruthy()
    },
}

export const Semantic = {
    args: { family: 'Semantic' },
    play: async ({ canvasElement }: Ctx) => {
        const foreground = canvasElement.querySelector<HTMLElement>('[data-token="--foreground"]')!
        await expect(foreground.dataset.tier).toBe('semantic')
        await expect(foreground.textContent).toContain('var(--fleet-yellow)')
    },
}

export const AlphaTints = {
    name: 'Alpha tints',
    args: { family: 'Alpha tints' },
    play: async ({ canvasElement }: Ctx) => {
        for (const name of ['--hairline', '--hairline-medium', '--hairline-strong', '--text-muted', '--surface-sunken'])
            await expect(canvasElement.querySelector(`[data-token="${name}"]`)).not.toBeNull()
    },
}

export const ColourBlind = {
    name: 'Colour-blind mode',
    args: { family: 'Colour-blind mode' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('[data-token="--fleet-red-blind"]')).not.toBeNull()
        await expect(canvasElement.querySelector('[data-token="--green-blind"]')).not.toBeNull()
    },
}

export const Glass = {
    name: 'Glass (effects)',
    args: { family: 'Glass (effects)' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(tokens(canvasElement).every((el) => /transparency|backdrop/.test(el.dataset.token!))).toBe(true)
    },
}

export const MetaGroups = {
    name: 'Item meta groups',
    args: { family: 'Item meta groups' },
    play: async ({ canvasElement }: Ctx) => {
        for (const name of ['--tech-i', '--tech-ii', '--tech-iii', '--faction', '--storyline', '--deadspace', '--officer', '--abyssal'])
            await expect(canvasElement.querySelector(`[data-token="${name}"]`)).not.toBeNull()
    },
}

export const SecurityStatus = {
    name: 'Security status',
    args: { family: 'Security status' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(tokens(canvasElement).length).toBe(11)
    },
}

export const Discord = {
    args: { family: 'Discord' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('[data-token="--discord-blurple"]')).not.toBeNull()
    },
}

export const SwatchesOnly = {
    name: 'Swatches only',
    args: { show_values: false, family: 'Brand palette' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('.value')).toBeNull()
    },
}
