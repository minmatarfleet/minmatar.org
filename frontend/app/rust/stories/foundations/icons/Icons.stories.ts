import { expect } from 'storybook/test'
import IconGallery from '../../../components/IconGallery.astro'
import { radio_control, select_control } from '../../_controls'

// Expected counts come from the same files the gallery renders.
const icon_files = Object.keys(import.meta.glob('/src/components/icons/**/*.astro')).map(path => path.slice('/src/components/icons/'.length))
const ALL = icon_files.length
// Icons with an inline <style> in their <svg>. happy-dom (vitest) drops everything after the first one,
// so there the cells after it are not counted; a real browser renders all of them.
const INLINE_STYLE = Object.entries(import.meta.glob('/src/components/icons/**/*.astro', { eager: true, query: '?raw', import: 'default' }))
    .filter(([, source]) => /<svg[\s\S]*<style>/.test(source as string)).length
const in_happy_dom = () => typeof navigator !== 'undefined' && /happy-?dom/i.test(navigator.userAgent)
// Cells lost to that bug, for a gallery that includes the inline-style icons (everything but `eve` and `buttons`).
const dropped = (includes_inline_style: boolean) => (in_happy_dom() && includes_inline_style ? Math.max(0, INLINE_STYLE - 1) : 0)
const EVE = icon_files.filter(file => /ev[e]?icon$/i.test(file.replace(/\.astro$/, ''))).length
const BUTTONS = icon_files.filter(file => file.startsWith('buttons/')).length
const MAIN = ALL - BUTTONS

type Play = { canvasElement: HTMLElement }

const cells = (canvasElement: HTMLElement) => Array.from(canvasElement.querySelectorAll('[data-icon-cell]'))

async function expect_labelled(canvasElement: HTMLElement, count: number, includes_inline_style = count !== EVE && count !== BUTTONS) {
    // The server rendered every icon of the folder, whatever the DOM did with them afterwards.
    await expect(Number(canvasElement.querySelector('.icon-gallery')?.getAttribute('data-total'))).toBe(count)
    const found = cells(canvasElement)
    await expect(found).toHaveLength(count - dropped(includes_inline_style))
    for (const cell of found) {
        const label = cell.querySelector('.icon-label')?.textContent?.trim()
        await expect(label, 'every icon cell has a label').toBeTruthy()
        await expect(label).toMatch(/\.astro$/)
        await expect(cell.querySelector('svg, img, div'), `${label} rendered nothing`).not.toBeNull()
    }
}

export default {
    title: 'Foundations/Icons/All icons',
    component: IconGallery,
    parameters: {
        layout: 'fullscreen',
        docs: {
            description: {
                component: [
                    'Every icon in `src/components/icons/`, rendered from the folder itself so a new icon shows up here without editing the story. Most are inline SVG that take their colour from `currentColor`; the `*EvEIcon` files are the in-game style PNGs and ignore `color` and `size`.',
                    'Only a few icons accept props (`size`, sometimes `xlink`), so the gallery passes `size` to those that declare it. The `buttons/` folder holds the 18-24px glyphs used inside `Button`.',
                    'Do not recolour icons with hardcoded values: set `color` on the parent from a token (`--foreground`, `--highlight`, `--fleet-red`).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        only: radio_control(['all', 'eve', 'buttons', 'main'] as const, 'Which icons to show: everything, the in-game style (`*EvEIcon`), the `buttons/` glyphs, or all but the buttons.'),
        size: { control: { type: 'range', min: 12, max: 128, step: 4 }, description: 'Pixel size passed to icons that accept a `size` prop.' },
        color: select_control(['var(--foreground)', 'var(--highlight)', 'var(--fleet-red)', 'var(--alliance-blue)', 'var(--green)', 'var(--fleet-yellow)', 'var(--militia-purple)'], 'Text colour the SVGs inherit through `currentColor`.'),
        background: select_control(['transparent', 'var(--fleet-red)', 'var(--alliance-blue)', 'var(--militia-purple)', 'var(--green)', 'var(--background)'], 'Gallery background token.'),
        min_item_width: { control: 'text', description: 'Minimum cell width for the grid.' },
    },
    args: {
        only: 'all',
        size: 32,
        color: 'var(--foreground)',
        background: 'transparent',
        min_item_width: '9rem',
    },
}

export const AllIcons = {
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement, ALL)
        await expect(canvasElement.querySelector('[data-icon="RifterIcon.astro"]')).not.toBeNull()
        await expect(canvasElement.querySelector('[data-icon="buttons/AddIcon.astro"]')).not.toBeNull()
    },
}

export const EveStyleIcons = {
    args: { only: 'eve' },
    play: async ({ canvasElement }: Play) => {
        await expect(EVE).toBeGreaterThan(10)
        await expect_labelled(canvasElement, EVE)
        for (const cell of cells(canvasElement))
            await expect(cell.querySelector('img'), `${cell.getAttribute('data-icon')} is an in-game image icon`).not.toBeNull()
    },
}

export const ButtonIcons = {
    args: { only: 'buttons', size: 24 },
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement, BUTTONS)
        for (const cell of cells(canvasElement))
            await expect(cell.getAttribute('data-icon')).toMatch(/^buttons\//)
    },
}

export const GeneralIcons = {
    args: { only: 'main' },
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement, MAIN)
    },
}

export const Sizes = {
    args: { only: 'main', size: 64 },
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement, MAIN)
        const flag = canvasElement.querySelector('[data-icon="FlagIcon.astro"] svg')
        await expect(flag).toHaveAttribute('width', '64')
        await expect(flag).toHaveAttribute('height', '64')
    },
}

export const SmallSize = {
    args: { only: 'main', size: 16 },
    play: async ({ canvasElement }: Play) => {
        const flag = canvasElement.querySelector('[data-icon="FlagIcon.astro"] svg')
        await expect(flag).toHaveAttribute('width', '16')
    },
}

export const OnFleetRed = {
    name: 'On a red background',
    args: { background: 'var(--fleet-red)', color: 'var(--button-color)' },
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement, ALL)
        const gallery = canvasElement.querySelector('.icon-gallery') as HTMLElement
        await expect(gallery.getAttribute('style')).toContain('--gallery_background: var(--fleet-red)')
        await expect(gallery.getAttribute('style')).toContain('--gallery_color: var(--button-color)')
    },
}

export const OnAllianceBlue = {
    name: 'On a blue background',
    args: { background: 'var(--alliance-blue)', color: 'var(--button-color)' },
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement, ALL)
        const gallery = canvasElement.querySelector('.icon-gallery') as HTMLElement
        await expect(gallery.getAttribute('style')).toContain('--gallery_background: var(--alliance-blue)')
    },
}

export const Highlighted = {
    args: { color: 'var(--highlight)', only: 'main' },
    play: async ({ canvasElement }: Play) => {
        const gallery = canvasElement.querySelector('.icon-gallery') as HTMLElement
        await expect(gallery.getAttribute('style')).toContain('--gallery_color: var(--highlight)')
        await expect(canvasElement.querySelector('.icon-gallery')).toHaveAttribute('data-total', String(MAIN))
    },
}

// Individual icons with their own props.
