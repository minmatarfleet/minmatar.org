const META_DESCRIPTION_MAX = 160

export interface FittingDetailSeoInput {
    fittingId: number
    fittingName: string
    shipName: string
    shipId: number
    description: string
    tagLabels: string[]
    updatedAt?: Date | string | null
    siteName: string
    siteOrigin: string
    fittingsListUrl: string
    shipsUrl: string
    canonicalUrl: string
    metaImage: string
}

export interface FittingListSeoEntry {
    id: number
    name: string
    shipName: string
    url: string
}

export interface FittingsListSeoInput {
    fittings: FittingListSeoEntry[]
    siteName: string
    siteOrigin: string
    fittingsListUrl: string
    shipsUrl: string
    canonicalUrl: string
    metaImage: string
}

type Translate = (key: string) => string

function truncateMetaDescription(text: string, max = META_DESCRIPTION_MAX): string {
    const normalized = text.replace(/\s+/g, ' ').trim()
    if (normalized.length <= max) return normalized

    const truncated = normalized.slice(0, max - 1)
    const lastSpace = truncated.lastIndexOf(' ')
    if (lastSpace > max * 0.6) return `${truncated.slice(0, lastSpace)}…`

    return `${truncated}…`
}

function formatIsoDate(value?: Date | string | null): string | undefined {
    if (!value) return undefined

    const date = value instanceof Date ? value : new Date(value)
    if (Number.isNaN(date.getTime())) return undefined

    return date.toISOString()
}

function buildTagsSuffix(tagLabels: string[], t: Translate): string {
    if (!tagLabels.length) return ''

    return t('fitting.detail.meta_description_tags_suffix')
        .replace('{tags}', tagLabels.join(', '))
}

export function buildFittingDetailMetaTitle(input: FittingDetailSeoInput, t: Translate): string {
    return t('fitting.detail.meta_title')
        .replace('{fitting}', input.fittingName)
        .replace('{ship}', input.shipName)
        .replace('{site}', input.siteName)
}

export function buildFittingDetailMetaDescription(input: FittingDetailSeoInput, t: Translate): string {
    const description = input.description.trim()
    if (description) return truncateMetaDescription(description)

    const tagsSuffix = buildTagsSuffix(input.tagLabels, t)

    return truncateMetaDescription(
        t('fitting.detail.meta_description_enriched')
            .replace('{fitting}', input.fittingName)
            .replace('{ship}', input.shipName)
            .replace('{tags_suffix}', tagsSuffix),
    )
}

export function buildFittingDetailJsonLd(input: FittingDetailSeoInput, metaTitle: string, metaDescription: string) {
    const dateModified = formatIsoDate(input.updatedAt)
    const keywords = [
        'EVE Online',
        'ship fitting',
        input.shipName,
        input.fittingName,
        ...input.tagLabels,
    ].filter(Boolean)

    return {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'WebSite',
                '@id': `${input.siteOrigin}/#website`,
                name: input.siteName,
                url: input.siteOrigin,
            },
            {
                '@type': 'WebPage',
                '@id': `${input.canonicalUrl}#webpage`,
                url: input.canonicalUrl,
                name: metaTitle,
                description: metaDescription,
                isPartOf: { '@id': `${input.siteOrigin}/#website` },
                primaryImageOfPage: { '@type': 'ImageObject', url: input.metaImage },
                breadcrumb: { '@id': `${input.canonicalUrl}#breadcrumb` },
                mainEntity: { '@id': `${input.canonicalUrl}#fitting` },
            },
            {
                '@type': 'BreadcrumbList',
                '@id': `${input.canonicalUrl}#breadcrumb`,
                itemListElement: [
                    {
                        '@type': 'ListItem',
                        position: 1,
                        name: 'Ships',
                        item: input.shipsUrl,
                    },
                    {
                        '@type': 'ListItem',
                        position: 2,
                        name: 'Fittings',
                        item: input.fittingsListUrl,
                    },
                    {
                        '@type': 'ListItem',
                        position: 3,
                        name: input.fittingName,
                        item: input.canonicalUrl,
                    },
                ],
            },
            {
                '@type': 'TechArticle',
                '@id': `${input.canonicalUrl}#fitting`,
                headline: `${input.fittingName} — ${input.shipName}`,
                name: input.fittingName,
                description: metaDescription,
                image: input.metaImage,
                about: {
                    '@type': 'Thing',
                    name: input.shipName,
                    identifier: input.shipId,
                },
                keywords: keywords.join(', '),
                inLanguage: 'en',
                publisher: {
                    '@type': 'Organization',
                    name: input.siteName,
                    url: input.siteOrigin,
                },
                mainEntityOfPage: { '@id': `${input.canonicalUrl}#webpage` },
                ...(dateModified ? { dateModified } : {}),
            },
        ],
    }
}

export function buildFittingsListMetaTitle(siteName: string, t: Translate): string {
    return t('fitting.list.meta_title').replace('{site}', siteName)
}

export function buildFittingsListMetaDescription(count: number, t: Translate): string {
    return truncateMetaDescription(
        t('fitting.list.meta_description').replace('{count}', count.toLocaleString('en')),
        165,
    )
}

export function buildFittingsListJsonLd(input: FittingsListSeoInput, metaTitle: string, metaDescription: string) {
    return {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'WebSite',
                '@id': `${input.siteOrigin}/#website`,
                name: input.siteName,
                url: input.siteOrigin,
            },
            {
                '@type': 'CollectionPage',
                '@id': `${input.canonicalUrl}#webpage`,
                url: input.canonicalUrl,
                name: metaTitle,
                description: metaDescription,
                isPartOf: { '@id': `${input.siteOrigin}/#website` },
                primaryImageOfPage: { '@type': 'ImageObject', url: input.metaImage },
                breadcrumb: { '@id': `${input.canonicalUrl}#breadcrumb` },
                mainEntity: { '@id': `${input.canonicalUrl}#itemlist` },
            },
            {
                '@type': 'BreadcrumbList',
                '@id': `${input.canonicalUrl}#breadcrumb`,
                itemListElement: [
                    {
                        '@type': 'ListItem',
                        position: 1,
                        name: 'Ships',
                        item: input.shipsUrl,
                    },
                    {
                        '@type': 'ListItem',
                        position: 2,
                        name: 'Fittings',
                        item: input.canonicalUrl,
                    },
                ],
            },
            {
                '@type': 'ItemList',
                '@id': `${input.canonicalUrl}#itemlist`,
                name: metaTitle,
                numberOfItems: input.fittings.length,
                itemListElement: input.fittings.slice(0, 50).map((fitting, index) => ({
                    '@type': 'ListItem',
                    position: index + 1,
                    name: `${fitting.name} — ${fitting.shipName}`,
                    url: fitting.url,
                })),
            },
        ],
    }
}
