import { expect } from 'storybook/test'
import ImageAssetGallery from '../../components/ImageAssetGallery.astro'

type Ctx = { canvasElement: HTMLElement }

const cells = (canvas: HTMLElement) => [...canvas.querySelectorAll<HTMLElement>('[data-asset]')]

const shows_folder = (folder: string) => async ({ canvasElement }: Ctx) => {
    const list = canvasElement.querySelector<HTMLElement>('.image-assets')!
    await expect(list.dataset.folder).toBe(folder)
    const items = cells(canvasElement)
    await expect(items.length).toBe(Number(list.dataset.total))
    await expect(items.length).toBeGreaterThan(0)
    for (const item of items) {
        const img = item.querySelector('img')!
        await expect(img.getAttribute('src')).toBe(item.dataset.asset)
        await expect(img.getAttribute('alt')).not.toBe('')
        await expect(item.querySelector('code')!.textContent).toBe(item.dataset.asset)
    }
}

export default {
    title: 'Foundations/Image icons and marks',
    component: ImageAssetGallery,
    parameters: {
        docs: {
            description: {
                component: [
                    'The raster and SVG icons the site serves from `public/images/`: EVE UI icons (`/images/icons/`), fleet group and ship class icons, and the brand marks for SIGs, teams and the fleet. Each cell shows the path to use in an `<img>` or `Picture`.',
                    'Vector icons that take a colour or size are Astro components (**Foundations › Icons**). Character, corporation and item images come from the EVE image server through the **EVE** components.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        folder: { control: 'select', options: ['eve-ui', 'groups', 'input-groups', 'ships', 'sigs', 'teams', 'fleet'], description: 'Which folder of public/images to show.' },
        size: { control: { type: 'range', min: 16, max: 128, step: 8 }, description: 'Display size in px (story only).' },
        background: { control: 'color', description: 'Background behind each icon (story only).' },
    },
    args: { folder: 'eve-ui', size: 48, background: 'transparent' },
}

export const EveUi = { name: 'EVE UI icons', play: shows_folder('eve-ui') }
export const Groups = { name: 'Fleet group icons', args: { folder: 'groups', size: 64 }, play: shows_folder('groups') }
export const InputGroups = { name: 'Input group icons', args: { folder: 'input-groups' }, play: shows_folder('input-groups') }
export const Ships = { name: 'Ship class icons', args: { folder: 'ships' }, play: shows_folder('ships') }
export const Sigs = { name: 'SIG marks', args: { folder: 'sigs', size: 80 }, play: shows_folder('sigs') }
export const Teams = { name: 'Team marks', args: { folder: 'teams', size: 80 }, play: shows_folder('teams') }
export const Fleet = { name: 'Fleet marks', args: { folder: 'fleet', size: 96, background: 'var(--fleet-red)' }, play: shows_folder('fleet') }
