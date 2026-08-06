interface CapitalGuideJsonLdOptions {
    canonicalUrl: string
    siteName: string
    siteOrigin: string
    metaTitle: string
    metaDescription: string
    metaImage: string
    guidesUrl: string
    authorName: string
    publisherName: string
    editionLabel: string
    keywords: string[]
}

export function buildCapitalGuideJsonLd(options: CapitalGuideJsonLdOptions) {
    const {
        canonicalUrl,
        siteName,
        siteOrigin,
        metaTitle,
        metaDescription,
        metaImage,
        guidesUrl,
        authorName,
        publisherName,
        editionLabel,
        keywords,
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
                        item: guidesUrl,
                    },
                    {
                        '@type': 'ListItem',
                        position: 2,
                        name: metaTitle,
                        item: canonicalUrl,
                    },
                ],
            },
            {
                '@type': 'Article',
                '@id': `${canonicalUrl}#article`,
                headline: metaTitle,
                description: metaDescription,
                image: metaImage,
                author: {
                    '@type': 'Person',
                    name: authorName,
                },
                publisher: {
                    '@type': 'Organization',
                    name: publisherName,
                    url: siteOrigin,
                },
                genre: 'Video game guide',
                keywords: keywords.join(', '),
                inLanguage: 'en',
                mainEntityOfPage: { '@id': `${canonicalUrl}#webpage` },
                version: editionLabel,
            },
        ],
    }
}
