import type { GuideMeta } from '@/data/guides/types'
import {
    GUIDES_INDEX_PATH,
    LEARNING_CENTER_PATH,
    LEARNING_HUB_PATH,
    guidePath,
} from '@/data/guides/urls'

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

export interface LandingSeo {
    metaTitle: string
    metaDescription: string
    canonicalUrl: string
    metaImage: string
    keywords: string[]
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
    return guide.path ?? guidePath(guide.slug)
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
    const guidesIndexUrl = new URL(translatePath(LEARNING_HUB_PATH), siteOrigin).href

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

function landingSeoFromKeys(options: {
    siteName: string
    siteOrigin: string
    translatePath: (path: string) => string
    t: Translate
    coverImage: string
    path: string
    titleKey: string
    descriptionKey: string
    keywordsKey: string
}): LandingSeo {
    const { siteName, siteOrigin, translatePath, t, coverImage, path, titleKey, descriptionKey, keywordsKey } = options
    const canonicalUrl = new URL(translatePath(path), siteOrigin).href

    return {
        metaTitle: t(titleKey).replace('{site}', siteName),
        metaDescription: truncateMetaDescription(t(descriptionKey)),
        canonicalUrl,
        metaImage: new URL(coverImage, siteOrigin).href,
        keywords: t(keywordsKey)
            .split(',')
            .map((keyword) => keyword.trim())
            .filter(Boolean),
    }
}

export function getGuidesIndexSeo(options: {
    siteName: string
    siteOrigin: string
    translatePath: (path: string) => string
    t: Translate
    coverImage: string
}): LandingSeo & { guidesIndexUrl: string } {
    const seo = landingSeoFromKeys({
        ...options,
        path: GUIDES_INDEX_PATH,
        titleKey: 'guides.seo.index.meta_title',
        descriptionKey: 'guides.seo.index.meta_description',
        keywordsKey: 'guides.seo.index.keywords',
    })

    return { ...seo, guidesIndexUrl: seo.canonicalUrl }
}

export function getLearningHubSeo(options: {
    siteName: string
    siteOrigin: string
    translatePath: (path: string) => string
    t: Translate
    coverImage: string
}): LandingSeo {
    return landingSeoFromKeys({
        ...options,
        path: LEARNING_HUB_PATH,
        titleKey: 'learning.seo.index.meta_title',
        descriptionKey: 'learning.seo.index.meta_description',
        keywordsKey: 'learning.seo.index.keywords',
    })
}

export function getLearningCenterSeo(options: {
    siteName: string
    siteOrigin: string
    translatePath: (path: string) => string
    t: Translate
    coverImage: string
}): LandingSeo {
    return landingSeoFromKeys({
        ...options,
        path: LEARNING_CENTER_PATH,
        titleKey: 'learning_center.seo.index.meta_title',
        descriptionKey: 'learning_center.seo.index.meta_description',
        keywordsKey: 'learning_center.seo.index.keywords',
    })
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
                        name: 'Learning',
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

export function buildLandingCollectionJsonLd(options: {
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

/** @deprecated Prefer buildLandingCollectionJsonLd */
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
    return buildLandingCollectionJsonLd(options)
}
