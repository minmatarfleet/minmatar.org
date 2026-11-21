import { expect } from 'storybook/test'
import LogoGallery from '../../../components/LogoGallery.astro'
import { select_control } from '../../_controls'

const logo_files = Object.keys(import.meta.glob('/src/components/logos/**/*.astro')).map(path => path.slice('/src/components/logos/'.length))
const LOGOS = logo_files.length

type Play = { canvasElement: HTMLElement }

const cells = (canvasElement: HTMLElement) => Array.from(canvasElement.querySelectorAll('[data-logo-cell]'))

async function expect_labelled(canvasElement: HTMLElement) {
    const found = cells(canvasElement)
    await expect(found).toHaveLength(LOGOS)
    for (const cell of found) {
        const label = cell.querySelector('.logo-label')?.textContent?.trim()
        await expect(label, 'every logo cell has a label').toBeTruthy()
        await expect(label).toMatch(/Logo\.astro$/)
        await expect(cell.querySelector('svg, img'), `${label} rendered nothing`).not.toBeNull()
    }
}

export default {
    title: 'Foundations/Icons/Logos',
    component: LogoGallery,
    parameters: {
        layout: 'fullscreen',
        docs: {
            description: {
                component: [
                    'The four empire logos in `src/components/logos/` (Amarr, Caldari, Gallente, Minmatar), rendered from the folder so a new logo appears without editing the story.',
                    'They are inline SVGs with their own faction fills and scale with their container (`w-full`); size them by wrapping them, as the gallery does with `size`. For the alliance mark use `FleetLogo` in `icons/`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        size: select_control(['var(--space-xl)', 'var(--space-2xl)', 'var(--space-3xl)'], 'Width and height of the frame each logo scales to.'),
        color: select_control(['var(--foreground)', 'var(--highlight)'], 'Text colour of the labels.'),
        background: select_control(['transparent', 'var(--fleet-red)', 'var(--alliance-blue)', 'var(--background)'], 'Gallery background token.'),
        min_item_width: { control: 'text', description: 'Minimum cell width for the grid.' },
    },
    args: {
        size: 'var(--space-3xl)',
        color: 'var(--foreground)',
        background: 'transparent',
        min_item_width: '10rem',
    },
}

export const AllLogos = {
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement)
        for (const name of ['AmarrLogo', 'CaldariLogo', 'GallenteLogo', 'MinmatarLogo'])
            await expect(canvasElement.querySelector(`[data-logo="${name}.astro"]`)).not.toBeNull()
    },
}

export const Small = {
    args: { size: 'var(--space-xl)' },
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement)
        const gallery = canvasElement.querySelector('.logo-gallery') as HTMLElement
        await expect(gallery.getAttribute('style')).toContain('--gallery_logo_size: var(--space-xl)')
    },
}

export const Large = {
    args: { size: 'var(--space-3xl)', min_item_width: '14rem' },
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement)
        const gallery = canvasElement.querySelector('.logo-gallery') as HTMLElement
        await expect(gallery.getAttribute('style')).toContain('--gallery_logo_size: var(--space-3xl)')
    },
}

export const OnRedBackground = {
    name: 'On a red background',
    args: { background: 'var(--fleet-red)' },
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement)
        const gallery = canvasElement.querySelector('.logo-gallery') as HTMLElement
        await expect(gallery.getAttribute('style')).toContain('--gallery_background: var(--fleet-red)')
    },
}

export const OnBlueBackground = {
    name: 'On a blue background',
    args: { background: 'var(--alliance-blue)' },
    play: async ({ canvasElement }: Play) => {
        await expect_labelled(canvasElement)
        const gallery = canvasElement.querySelector('.logo-gallery') as HTMLElement
        await expect(gallery.getAttribute('style')).toContain('--gallery_background: var(--alliance-blue)')
    },
}
