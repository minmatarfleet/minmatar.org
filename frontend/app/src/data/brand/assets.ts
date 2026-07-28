export type BrandAssetSize = '512' | '1080' | '2160'

export interface BrandAssetRow {
    name: string
    description: string
    svg?: string
    png64?: string
    png128?: string
    png256?: string
    png512?: string
    png1080?: string
    png2160?: string
}

export type BrandAssetColumn = {
    key: keyof BrandAssetRow
    label: string
}

export const logoAssetColumns: BrandAssetColumn[] = [
    { key: 'svg', label: 'SVG' },
    { key: 'png512', label: '512px' },
    { key: 'png1080', label: '1080px' },
    { key: 'png2160', label: '2160px' },
]

export const mascotAssetColumns: BrandAssetColumn[] = [
    { key: 'png512', label: '512px' },
    { key: 'png256', label: '256px' },
    { key: 'png128', label: '128px' },
    { key: 'png64', label: '64px' },
]

export const brandColors = [
    { name: 'Gold', hex: '#F1D9A0' },
    { name: 'Red', hex: '#B53620' },
] as const

export const brandFont = {
    name: 'Norwester',
    url: 'https://jamiewilson.io/norwester/',
} as const

export const animatedLogoUrl = 'https://imgur.com/FpMFPu0'

export const logoAssets: BrandAssetRow[] = [
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
    {
        name: 'BUILD',
        description: 'Current logo',
        svg: '/images/brand/fleet/build_logo.svg',
        png512: '/images/brand/fleet/build_512.png',
    },
]

export const mascotAssets: BrandAssetRow[] = [
    {
        name: 'Scurry',
        description: 'Scurry — FL33T mascot',
        png512: '/images/brand/scurry.png',
    },
    {
        name: 'Sneak idle',
        description: 'Sneak — idle',
        png512: '/images/sneak-idle.png',
    },
    {
        name: 'Sneak present',
        description: 'Sneak — with present',
        png512: '/images/sneak-present-icon.png',
        png256: '/images/sneak-present-icon-256.png',
        png128: '/images/sneak-present-icon-128.png',
        png64: '/images/sneak-present-icon-64.png',
    },
    {
        name: 'Sneak tip-toe',
        description: 'Sneak — tip-toe',
        png512: '/images/sneak.png',
    },
    {
        name: 'Sneak duck',
        description: 'Sneak — rubber duck',
        png512: '/images/sneak-duck.png',
    },
    {
        name: 'Sneak coffee',
        description: 'Sneak — coffee',
        png512: '/images/sneak-coffee.png',
    },
]
