// Every image, background and video the site ships, split into the
// collections Foundations › Imagery shows. Plain data, so story files can
// import it; testing/rust/imagery.test.ts fails when a file under public/
// images, public/videos or src/assets is in no collection.

export interface ImageryCollection {
    id:             string;
    title:          string;
    description:    string;
    root:           'public' | 'src';
    dir:            string;             // relative to the root
    recursive?:     boolean;
    match?:         string;             // regex on the file name
    exclude?:       string;             // regex on the file name
    layout:         'wide' | 'grid' | 'video';
}

export const IMAGERY_COLLECTIONS: ImageryCollection[] = [
    { id: 'covers', title: 'Page covers', description: 'Full-bleed page backgrounds (PageLanding, PageWide covers). The -990 file is the narrow-screen crop.', root: 'public', dir: 'images', match: '-cover', layout: 'wide' },
    { id: 'cards', title: 'Cards', description: 'Card and tile art for guides, tribes and services.', root: 'public', dir: 'images', match: '-card', layout: 'wide' },
    { id: 'site-images', title: 'Other site images', description: 'Everything else at the top of /images: logos, posters, thumbnails, seasonal art, app icons.', root: 'public', dir: 'images', exclude: '-cover|-card', layout: 'grid' },
    { id: 'favicons', title: 'Favicon', description: 'The site icon at the root of public/.', root: 'public', dir: '', layout: 'grid' },
    { id: 'brand', title: 'Brand marks', description: 'Fleet, SIG and team marks (also on the Branding page).', root: 'public', dir: 'images/brand', recursive: true, layout: 'grid' },
    { id: 'corporations', title: 'Corporation art', description: 'The art each member corporation\'s page and slide uses.', root: 'public', dir: 'images/corporations', recursive: true, layout: 'wide' },
    { id: 'ui-icons', title: 'EVE UI icons', description: 'Raster UI, fleet group, input group and ship class icons.', root: 'public', dir: 'images/icons', recursive: true, layout: 'grid' },
    { id: 'guides', title: 'Guides', description: 'Screenshots, maps and diagrams in the guides.', root: 'public', dir: 'images/guides', recursive: true, layout: 'wide' },
    { id: 'newsletter', title: 'Newsletter', description: 'Images in the monthly Fleet Dispatch issues.', root: 'public', dir: 'images/newsletter', recursive: true, layout: 'wide' },
    { id: 'campaigns', title: 'Campaigns', description: 'Campaign write-up and Reddit post images.', root: 'public', dir: 'images/campaigns', recursive: true, layout: 'wide' },
    { id: 'warzone', title: 'Warzone report', description: 'Logos and art in the monthly Warzone Report.', root: 'public', dir: 'images/warzone', recursive: true, layout: 'grid' },
    { id: 'rat-chronicle', title: 'Rat Chronicle', description: 'Art in the Rat Chronicle.', root: 'public', dir: 'images/rat-chronicle', recursive: true, layout: 'wide' },
    { id: 'bug-icons', title: 'Bug icons', description: 'The icons the bug-report easter egg uses.', root: 'public', dir: 'images/bug_icons', recursive: true, layout: 'grid' },
    { id: 'planets', title: 'Planet textures', description: 'Planet type art bundled with the app (src/assets), for PI and moon pages.', root: 'src', dir: 'assets', recursive: true, layout: 'grid' },
    { id: 'uploads', title: 'Uploads', description: 'Images uploaded into public/uploads.', root: 'public', dir: 'uploads', recursive: true, layout: 'wide' },
    { id: 'videos', title: 'Video loops', description: 'Background loops and tutorials in public/videos.', root: 'public', dir: 'videos', recursive: true, layout: 'video' },
]

export const IMAGE_EXTENSIONS = /\.(jpe?g|png|webp|avif|gif|svg)$/i
export const VIDEO_EXTENSIONS = /\.(webm|mp4|mov)$/i

// The same picture in several files: name.jpg, name-990.jpg, name.webp, name-c.webp.
export const variant_key = (file: string) =>
    file.replace(/\.[a-z0-9]+$/i, '').replace(/-(990y?|c)$/i, '')

export function in_collection(collection: ImageryCollection, relative: string) {
    const media = collection.layout === 'video' ? VIDEO_EXTENSIONS : IMAGE_EXTENSIONS
    if (!media.test(relative))
        return false
    const prefix = collection.dir ? `${collection.dir}/` : ''
    if (prefix && !relative.startsWith(prefix))
        return false
    const rest = relative.slice(prefix.length)
    if (!collection.recursive && rest.includes('/'))
        return false
    const name = rest.split('/').pop()!
    if (collection.match && !new RegExp(collection.match).test(name))
        return false
    if (collection.exclude && new RegExp(collection.exclude).test(name))
        return false
    return true
}
