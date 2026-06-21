export type BrandAssetSize = '512' | '1080' | '2160'

export interface BrandAssetRow {
    name: string
    description: string
    svg?: string
    png512?: string
    png1080?: string
    png2160?: string
}

export const brandColors = [
    { name: 'Gold', hex: '#F1D9A0' },
    { name: 'Red', hex: '#B53620' },
] as const

export const brandFont = {
    name: 'Norwester',
    url: 'https://jamiewilson.io/norwester/',
} as const

export const animatedLogoUrl = 'https://imgur.com/FpMFPu0'

export const fleetAssets: BrandAssetRow[] = [
    {
        name: 'FL33T with banner',
        description: 'Current logo with banner',
        svg: '/images/brand/fleet/fl33t_logo.svg',
        png512: '/images/brand/fleet/fl33t_512.png',
    },
    {
        name: 'FL33T without banner',
        description: 'Current logo without banner',
        svg: '/images/brand/fleet/fl33t_logo.svg',
        png512: '/images/brand/fleet/fl33t_512.png',
    },
    {
        name: 'FL33T vintage',
        description: 'Old logo',
        png512: '/images/brand/fleet/fl33tvintage.png',
    },
]

export const buildAssets: BrandAssetRow[] = [
    {
        name: 'BUILD',
        description: 'Current logo',
        svg: '/images/brand/fleet/build_logo.svg',
        png512: '/images/brand/fleet/build_512.png',
    },
]

const sigSlugs = [
    { slug: 'blackops', name: 'Blackops' },
    { slug: 'capitals', name: 'Capitals' },
    { slug: 'wormholes', name: 'Wormholes' },
    { slug: 'abyss', name: 'Abyss' },
    { slug: 'smallgang', name: 'Small Gang' },
    { slug: 'ganking', name: 'Ganking' },
] as const

export const sigAssets: BrandAssetRow[] = sigSlugs.map(({ slug, name }) => ({
    name,
    description: name,
    svg: `/images/brand/sigs/${slug}.svg`,
    png512: `/images/brand/sigs/${slug}_512.png`,
    png1080: `/images/brand/sigs/${slug}_1080.png`,
    png2160: `/images/brand/sigs/${slug}_2160.png`,
}))

const teamSlugs = [
    { slug: 'conversion', name: 'Conversion' },
    { slug: 'fitting', name: 'Fitting' },
    { slug: 'fleetcommand', name: 'Fleet Command' },
    { slug: 'people', name: 'People' },
    { slug: 'thinkspeak', name: 'Thinkspeak' },
    { slug: 'technology', name: 'Technology' },
    { slug: 'supply', name: 'Supply' },
    { slug: 'wiki', name: 'Wiki' },
] as const

export const teamAssets: BrandAssetRow[] = teamSlugs.map(({ slug, name }) => ({
    name,
    description: name,
    svg: `/images/brand/teams/${slug}.svg`,
    png512: `/images/brand/teams/${slug}_512.png`,
    png1080: `/images/brand/teams/${slug}_1080.png`,
    png2160: `/images/brand/teams/${slug}_2160.png`,
}))

export const mascotImage = '/images/brand/scurry.png'
