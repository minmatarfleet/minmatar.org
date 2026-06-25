import type { GuideMeta } from '@/data/guides/types'

const META_DESCRIPTION_MAX = 160

type Translate = (key: string) => string

export interface GuidePageSeo {
    metaTitle: string
    metaDescription: string
    canonicalUrl: string
    metaImage: string
    keywords: string[]
    guidesIndexUrl: string
}

export interface GuideJsonLdInput extends GuidePageSeo {
    guide: GuideMeta
    siteName: string
    siteOrigin: string
}

function truncateMetaDescription(text: string, max = META_DESCRIPTION_MAX): string {
    const normalized = text.replace(/\s+/g, ' ').trim()
    if (normalized.length <= max) return normalized

    const truncated = normalized.slice(0, max - 1)
    const lastSpace = truncated.lastIndexOf(' ')
    if (lastSpace > max * 0.6) return `${truncated.slice(0, lastSpace)}…`

    return `${truncated}…`
}

export function getGuideCanonicalPath(guide: Pick<GuideMeta, 'slug' | 'path'>): string {
    return guide.path ?? `/guides/${guide.slug}/`
}

function seoKey(slug: string, field: 'meta_title' | 'meta_description' | 'keywords'): string {
    return `guides.seo.${slug}.${field}`
}

export function getGuidePageSeo(options: {
    guide: GuideMeta
    siteName: string
    siteOrigin: string
    translatePath: (path: string) => string
    t: Translate
    coverImage: string
}): GuidePageSeo {
    const { guide, siteName, siteOrigin, translatePath, t, coverImage } = options
    const canonicalPath = getGuideCanonicalPath(guide)
    const canonicalUrl = new URL(translatePath(canonicalPath), siteOrigin).href
    const guidesIndexUrl = new URL(translatePath('/guides/'), siteOrigin).href

    const metaTitle = (t(seoKey(guide.slug, 'meta_title')) || `${guide.title} | ${siteName}`)
        .replace('{site}', siteName)
    const metaDescription = truncateMetaDescription(
        t(seoKey(guide.slug, 'meta_description')) || guide.excerpt,
    )
    const keywordsRaw = t(seoKey(guide.slug, 'keywords'))
    const keywords = keywordsRaw
        ? keywordsRaw.split(',').map((keyword) => keyword.trim()).filter(Boolean)
        : []

    return {
        metaTitle,
        metaDescription,
        canonicalUrl,
        metaImage: new URL(coverImage, siteOrigin).href,
        keywords,
        guidesIndexUrl,
    }
}

export function getGuidesIndexSeo(options: {
    siteName: string
    siteOrigin: string
    translatePath: (path: string) => string
    t: Translate
    coverImage: string
}): Omit<GuidePageSeo, 'guidesIndexUrl'> & { guidesIndexUrl: string } {
    const { siteName, siteOrigin, translatePath, t, coverImage } = options
    const guidesIndexUrl = new URL(translatePath('/guides/'), siteOrigin).href

    return {
        metaTitle: t('guides.seo.index.meta_title').replace('{site}', siteName),
        metaDescription: truncateMetaDescription(t('guides.seo.index.meta_description')),
        canonicalUrl: guidesIndexUrl,
        metaImage: new URL(coverImage, siteOrigin).href,
        keywords: t('guides.seo.index.keywords')
            .split(',')
            .map((keyword) => keyword.trim())
            .filter(Boolean),
        guidesIndexUrl,
    }
}

export function buildGuideJsonLd(input: GuideJsonLdInput) {
    const {
        guide,
        siteName,
        siteOrigin,
        metaTitle,
        metaDescription,
        canonicalUrl,
        metaImage,
        keywords,
        guidesIndexUrl,
    } = input

    const keywordList = [
        'EVE Online',
        guide.category,
        guide.title,
        ...keywords,
    ].filter(Boolean)

    return {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'WebSite',
                '@id': `${siteOrigin}/#website`,
                name: siteName,
                url: siteOrigin,
            },
            {
                '@type': 'WebPage',
                '@id': `${canonicalUrl}#webpage`,
                url: canonicalUrl,
                name: metaTitle,
                description: metaDescription,
                isPartOf: { '@id': `${siteOrigin}/#website` },
                primaryImageOfPage: { '@type': 'ImageObject', url: metaImage },
                breadcrumb: { '@id': `${canonicalUrl}#breadcrumb` },
                mainEntity: { '@id': `${canonicalUrl}#article` },
            },
            {
                '@type': 'BreadcrumbList',
                '@id': `${canonicalUrl}#breadcrumb`,
                itemListElement: [
                    {
                        '@type': 'ListItem',
                        position: 1,
                        name: 'Guides',
                        item: guidesIndexUrl,
                    },
                    {
                        '@type': 'ListItem',
                        position: 2,
                        name: guide.title,
                        item: canonicalUrl,
                    },
                ],
            },
            {
                '@type': 'Article',
                '@id': `${canonicalUrl}#article`,
                headline: guide.title,
                description: metaDescription,
                image: metaImage,
                author: guide.authors.map((author) => ({
                    '@type': author.entity === 'character' ? 'Person' : 'Organization',
                    name: author.name,
                })),
                publisher: {
                    '@type': 'Organization',
                    name: siteName,
                    url: siteOrigin,
                },
                articleSection: guide.category,
                genre: 'Video game guide',
                keywords: keywordList.join(', '),
                inLanguage: 'en',
                mainEntityOfPage: { '@id': `${canonicalUrl}#webpage` },
            },
        ],
    }
}

export function buildGuidesIndexJsonLd(options: {
    siteName: string
    siteOrigin: string
    metaTitle: string
    metaDescription: string
    canonicalUrl: string
    metaImage: string
    guides: Pick<GuideMeta, 'title' | 'slug' | 'path' | 'excerpt'>[]
    translatePath: (path: string) => string
}) {
    const {
        siteName,
        siteOrigin,
        metaTitle,
        metaDescription,
        canonicalUrl,
        metaImage,
        guides,
        translatePath,
    } = options

    return {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'WebSite',
                '@id': `${siteOrigin}/#website`,
                name: siteName,
                url: siteOrigin,
            },
            {
                '@type': 'CollectionPage',
                '@id': `${canonicalUrl}#webpage`,
                url: canonicalUrl,
                name: metaTitle,
                description: metaDescription,
                isPartOf: { '@id': `${siteOrigin}/#website` },
                primaryImageOfPage: { '@type': 'ImageObject', url: metaImage },
                mainEntity: {
                    '@type': 'ItemList',
                    itemListElement: guides.map((guide, index) => ({
                        '@type': 'ListItem',
                        position: index + 1,
                        name: guide.title,
                        url: new URL(translatePath(getGuideCanonicalPath(guide)), siteOrigin).href,
                        description: guide.excerpt,
                    })),
                },
            },
        ],
    }
}
