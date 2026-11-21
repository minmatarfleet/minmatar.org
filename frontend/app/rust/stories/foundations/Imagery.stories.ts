import { expect } from 'storybook/test'
import ImageryGallery from '../../components/ImageryGallery.astro'
import { IMAGERY_COLLECTIONS } from '../../foundations/imagery_collections'

type Ctx = { canvasElement: HTMLElement }

// Each collection renders every picture once, with the URL a page uses and a
// real preview (testing/rust/imagery.test.ts checks every file has a home).
const shows = (id: string) => async ({ canvasElement }: Ctx) => {
    const section = canvasElement.querySelector<HTMLElement>('[data-collection]')!
    await expect(section.dataset.collection).toBe(id)
    const items = [...canvasElement.querySelectorAll<HTMLElement>('[data-key]')]
    await expect(items.length).toBe(Number(section.dataset.total))
    await expect(items.length).toBeGreaterThan(0)
    for (const item of items) {
        const media = item.querySelector('img, video')!
        await expect(media).not.toBeNull()
        await expect(media.getAttribute('src')).toBeTruthy()
        await expect(item.querySelector('.url')!.textContent).toBe(item.dataset.url)
    }
}

export default {
    title: 'Foundations/Imagery',
    component: ImageryGallery,
    parameters: {
        docs: {
            description: {
                component: [
                    'Every image, background and video the site ships, read from `public/images`, `public/videos` and `src/assets` when the page renders: page covers, card art, brand marks, corporation art, guide and newsletter images, UI icons, planet textures and background loops.',
                    'Each picture appears once, with the path a page uses; its variants (the `-990` narrow-screen crop, `.webp` copies) are listed under it. A file that fits no collection fails `testing/rust/imagery.test.ts`, so new art always shows up here.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        collection: { control: 'select', options: IMAGERY_COLLECTIONS.map((c) => c.id), description: 'Which collection to show.' },
        limit: { control: { type: 'number', min: 1 }, description: 'Show the first N only.' },
        background: { control: 'color', description: 'Background behind each picture (grid collections).' },
    },
    args: { collection: 'covers' },
}

export const Covers = { name: 'Page covers', args: { collection: 'covers' }, play: shows('covers') }
export const Cards = { name: 'Cards', args: { collection: 'cards' }, play: shows('cards') }
export const SiteImages = { name: 'Other site images', args: { collection: 'site-images' }, play: shows('site-images') }
export const Favicons = { name: 'Favicon', args: { collection: 'favicons', background: 'var(--fleet-red)' }, play: shows('favicons') }
export const Brand = { name: 'Brand marks', args: { collection: 'brand' }, play: shows('brand') }
export const Corporations = { name: 'Corporation art', args: { collection: 'corporations' }, play: shows('corporations') }
export const UiIcons = { name: 'EVE UI icons', args: { collection: 'ui-icons' }, play: shows('ui-icons') }
export const Guides = { name: 'Guides', args: { collection: 'guides' }, play: shows('guides') }
export const Newsletter = { name: 'Newsletter', args: { collection: 'newsletter' }, play: shows('newsletter') }
export const Campaigns = { name: 'Campaigns', args: { collection: 'campaigns' }, play: shows('campaigns') }
export const Warzone = { name: 'Warzone report', args: { collection: 'warzone' }, play: shows('warzone') }
export const RatChronicle = { name: 'Rat Chronicle', args: { collection: 'rat-chronicle' }, play: shows('rat-chronicle') }
export const BugIcons = { name: 'Bug icons', args: { collection: 'bug-icons' }, play: shows('bug-icons') }
export const Planets = { name: 'Planet textures', args: { collection: 'planets' }, play: shows('planets') }
export const Uploads = { name: 'Uploads', args: { collection: 'uploads' }, play: shows('uploads') }
export const Videos = { name: 'Video loops', args: { collection: 'videos' }, play: shows('videos') }
